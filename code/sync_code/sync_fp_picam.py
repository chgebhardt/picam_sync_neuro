# Standard Library Imports
import os
import re
import pickle
import glob
import inspect
from datetime import datetime
from pathlib import Path

# Third-Party Libraries
import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression, TheilSenRegressor
import matplotlib.pyplot as plt
import cv2
from tqdm import tqdm


def synchronize_FP_picams(homedir, expID, picam_dict, fp_dict, verbose=False):
    '''
    Main function for synchronizing two picameras (slaves) with the Fiber photometry system (master).
    Input are the two dictionaries (for fp and the picams) which contain the Arduino flips and the LED blinks.
    '''
    folder = os.path.join(homedir, expID, '04_pickle_snapshots')
    function_name = inspect.currentframe().f_code.co_name

    # Attempt to load an existing sync_dict
    sync_dict = load_sync_pickle_file(homedir, expID)

    if sync_dict:
        print('\n-------------------------------------------------------------------------------------------------------------')
        print(f"\n[{datetime.now():%H:%M:%S}] ({function_name}) Found and loaded existing PICAM_FP_sync data previously saved on {sync_dict['sync_data_save_datetime']}!")
    
    else:
        print('\n-------------------------------------------------------------------------------------------------------------')
        print(f'\n[{datetime.now():%H:%M:%S}] ({function_name}) Synchronizing FP and picam data for experiment {expID}\n                                   using ROI intensity-voltage matching of the same blinking LED.')

        sync_dict = initialize_sync_dict(homedir, expID, picam_dict, fp_dict, verbose)

    # Print sync summary stats
    print(f'\n[{datetime.now():%H:%M:%S}] ({function_name}) PICAM-FP synchronization SUMMARY:\n')

    for picam_id in sync_dict['picam_list']:
        print(f'            {picam_id}-FP lag (sec): {sync_dict[picam_id]["lag_picam_sec"] - fp_dict["fp_timing"]["arduino_voltage"].iloc[0, 0]:.4f}')

    if sync_dict['picam_list'] == ['pic1', 'pic2']:
        print(f'            lagPicam1-lagPicam2 (sec): '
              f'{sync_dict["pic1"]["lag_picam_sec"] - sync_dict["pic2"]["lag_picam_sec"]:.4f}')
 
    return sync_dict

def initialize_sync_dict(homedir, expID, picam_dict, fp_dict, verbose):
    '''
    Initializes the sync_dict by performing synchronization of FP and picam data.
    '''
    function_name = inspect.currentframe().f_code.co_name

    sync_dict = {
        'expID': expID,
        'sync_data_save_datetime': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        'picam_list': [],
        'PICAM_FP_sync_run': False
    }

    arduino_voltage = fp_dict['fp_timing']['arduino_voltage'].copy()
    arduino2fp_flips = fp_dict['fp_timing']['digital_IOs']['Input0'].copy()

    picam_list = find_picams(homedir, expID)
    sync_dict['picam_list'] = picam_list

    for picam_id in picam_list:
        sync_dict[picam_id] = {}

        picam_LEDsignal = picam_dict[picam_id]['picam_timing']['picam_LEDsignal'].copy()
        picam_LED_blinks = picam_dict[picam_id]['picam_timing']['picam_LED_blinks'].copy()

        print(f"\n[{datetime.now():%H:%M:%S}] ({function_name}) Calculate lag between FP signal and {picam_id} using cross-correlation.")
        lag_picam_sec = calculate_lag_xcorr(picam_LEDsignal, arduino_voltage, new_timebase_s=0.01)

        model_picam, _ = determine_picam_FP_drift_and_plot(picam_LED_blinks, arduino2fp_flips, lag_picam_sec, picam_id, verbose)

        picam_LEDsignal_drft_corr = apply_lag_then_drift_picam_correction(picam_LEDsignal, lag_picam_sec, model_picam)
        picam_LED_blinks_drft_corr = apply_lag_then_drift_picam_correction(picam_LED_blinks, lag_picam_sec, model_picam)

        # Map the opto pulse train start and end times to picam frame number
        opto_pulse_train_timing = fp_dict['fp_timing']['opto_pulse_train_timing'].copy()
        opto_pulse_train_timing = map_fp_time_to_picam_frames(opto_pulse_train_timing, picam_id, picam_LEDsignal_drft_corr)

        sync_dict[picam_id]['lag_picam_sec'] = lag_picam_sec
        sync_dict[picam_id]['model_parameters'] = [model_picam.coef_[0], model_picam.intercept_]
        sync_dict[picam_id]['picam_LEDsignal_drft_corr'] = picam_LEDsignal_drft_corr
        sync_dict[picam_id]['picam_LED_blinks_drft_corr'] = picam_LED_blinks_drft_corr
        sync_dict[picam_id]['opto_pulse_train_timing'] = opto_pulse_train_timing

    sync_dict['PICAM_FP_sync_run'] = True

    return sync_dict



def find_picams(homedir, expID):
    '''
    Finds unique picam modifiers (pic1, pic2, ...) in the working folder.
    Only processes .txt files.
    '''
    
    function_name = inspect.currentframe().f_code.co_name
    
    folder = os.path.join(homedir, expID, '01_picams', '01_raw')

    # Get unique picam identifiers from .txt files containing 'pic'
    picam_identifiers = {re.split('[_.]', f)[2] for f in os.listdir(folder) 
                         if f.endswith('.txt') and 'pic' in f and len(re.split('[_.]', f)) > 2}

    picam_list = sorted(picam_identifiers)  # Sort the unique identifiers
    
    if not picam_list:
        print(f"\n[{datetime.now():%H:%M:%S}] ({function_name}) No picameras found in folder: {folder}")
        return []
    
    return picam_list


def calculate_lag_xcorr(df1, df2, new_timebase_s=0.01):
    """
    Resamples and finds lag between picamera LED traces (df1) and arduino_voltage trace (df2).
    The default resampling rate is 100 Hz (10 ms timebase).
    """

    df1_resampled = resample_signal(df1, 'frame_time_sec', 'LED_ROI_avg', new_timebase_s)
    df2_resampled = resample_signal(df2,    'fp_time_sec', 'voltage',     new_timebase_s)
    
    lag_picam_sec, _ = xcorr(df1_resampled, df2_resampled)
    lag_picam_sec   += df2['fp_time_sec'].iloc[0]  # Add the first timestamp from df2 to the lag

    return lag_picam_sec


def resample_signal(df, time_col, data_col, new_timebase_s):
    """
    Resample input DataFrame to a new timebase using linear interpolation.
    
    Parameters:
        df          : Input DataFrame.
        time_col    : Column name for the time data.
        data_col    : Column name for the data points.
        new_timebase_s : Desired timebase for resampling (in seconds).
        
    Returns:
        pd.DataFrame with resampled time and data points.
    """
    time_vector_interp = np.arange(df[time_col].iloc[0], df[time_col].iloc[-1] + new_timebase_s, new_timebase_s)
    data_points_interp = np.interp(time_vector_interp, df[time_col], df[data_col])
    
    # Create a new DataFrame with the interpolated results
    return pd.DataFrame({time_col: time_vector_interp, data_col: data_points_interp})


def xcorr(df1, df2):
    """
    Computes the cross-correlation between picam_LEDs (df1) and arduino_voltage (df2),
    returns the lag of df1 with respect to df2 and adjusts df1_time such that df1 and df2 are aligned.
    """
    
    # Extract the time and data columns
    time_df1, x = df1['frame_time_sec'].to_numpy(), df1['LED_ROI_avg'].to_numpy()
    time_df2, y = df2['fp_time_sec'].to_numpy(), df2['voltage'].to_numpy()

    # Perform cross-correlation
    corrCoeff = np.correlate(y, x, 'full')
    lagsOut   = np.arange(-len(x), len(y)-1)

    # Find the lag corresponding to the maximum correlation coefficient
    lag         = lagsOut[np.argmax(corrCoeff)]
    lag_pic_sec = time_df1[lag]

    return lag_pic_sec, df1


def determine_picam_FP_drift_and_plot(df1, df2, lag_picam_sec, picam_id, verbose=True):
    '''
    Determines the drift between the picamera time and FP time after applying a lag correction.
    This function fits a linear regression model to the time difference between picam LED blinks 
    and FP flips, corrects for any drift, and plots the results.

    Parameters:
        df1 (pd.DataFrame): DataFrame containing picam LED blink data. Must include 'fp_time_sec' 
                             (FP time) and 'flip_minus_blink_time' (time difference between flip and blink).
        df2 (pd.DataFrame): DataFrame containing FP flip data. Must include 'fp_time_sec' (FP time).
        lag_picam_sec (float): The lag correction to apply to the picamera time in seconds.
        picam_id (str): The identifier for the picamera, used in the plot title and print statements.
        verbose (bool, optional): If True, prints out the slope and intercept of the linear regression model 
                                  and displays the plots. Default is True.

    Returns:
        model (LinearRegression): The trained linear regression model that describes the drift.
        df (pd.DataFrame): The DataFrame with outliers removed and drift correction applied.
    '''
    function_name = inspect.currentframe().f_code.co_name

    # Step 1: Apply lag correction to picam time
    df1 = apply_lag_picam_correction(df1, lag_picam_sec)
    
    # Step 2: Find FP-flip-LED-blink pairs
    df = find_flip_blink_pairs(df1, df2)
    print(f"[{datetime.now():%H:%M:%S}] ({function_name}) {len(df)} Blink-Flip pairs found for {picam_id}.")
    
    # Step 3: Find and remove outliers by fitting a linear curve and then replace the outliers by their predicted value
    time_diff_threshold_sec = 0.03
    df, _, _ = find_outliers_regression(df, picam_id, time_diff_threshold_sec)
    
    # Step 4: Prepare data for linear regression model
    x = df['fp_time_sec'].values.reshape((-1, 1))  # Independent variable (FP time)
    y = df['flip_minus_blink_time'].values  # Dependent variable (time difference between flip and blink)
    
    # Step 5: Fit another linear model of (FP-camera) time difference vs. FP time this time with corrected outliers
    model = LinearRegression()
    model.fit(x, y)
    
    # Step 6: Predict the time difference based on the model
    y_pred = model.predict(x)
    
    if verbose:
        function_name = inspect.currentframe().f_code.co_name
        
        # Print model coefficients
        print(f"\n[{datetime.now():%H:%M:%S}] ({function_name}) {picam_id:} slope:     {model.coef_[0]:.6f}\n"
              f"{' ' * 47}{picam_id:} intercept:  {model.intercept_:.6f}\n")

        # Step 7: Plotting the results
        # Create a figure and axes for two subplots
        fig, axs = plt.subplots(nrows=1, ncols=2, figsize=(12, 5), constrained_layout=True)
        
        # Plot raw data and the regression line
        axs[0].plot(df['fp_time_sec'], df['flip_minus_blink_time'], 'o', label=f'{picam_id}: Flip-Blink Pairs', markersize=2, color='tab:blue')
        axs[0].plot(df['fp_time_sec'], model.coef_ * df['fp_time_sec'] + model.intercept_, 'k', linewidth=3)
        
        # Add grey horizontal line at y=0 (highest zorder, at the front)
        axs[0].axhline(y=0, color='grey', linewidth=2, linestyle='-', zorder=5)
        
        # Add textbox in the lower left corner of axs[0]
        # Compute the x-coordinate where the regression line intersects y=0
        
        intersection_time = -model.intercept_ / model.coef_[0]  # Solve model.coef_ * x + model.intercept_ = 0
        
        # Add a multi-line textbox in the lower left corner of axs[0]
        textbox_text = (
            f'Above the grey line, the {picam_id} signal was acquired faster \nthan the FP signal and vice versa below the grey line.\n\nReversal timepoint: {intersection_time:.1f} sec'
        )
        
        textbox = axs[0].text(
            0.05, 0.05,  # Position in axes fraction
            textbox_text,  # Display the multi-line message
            transform=axs[0].transAxes,  # Use axes coordinates
            fontsize=10, color='black', weight='normal',
            bbox=dict(facecolor='white', edgecolor='red', boxstyle='round,pad=0.5', linewidth=1),
            zorder = 5
        )
        
        # Now, position the arrow close to the center of the textbox (adjusting the x and y offsets)
        axs[0].annotate(
            '',  # No text needed for the arrow itself
            xy=(intersection_time, 0),  # Intersection point on the regression line
            xytext=(0.10, 0.05),  # Textbox location (in axes fraction)
            textcoords='axes fraction', # Ensure the textbox coordinates are interpreted as axes fraction
            arrowprops=dict(facecolor='red', edgecolor='red', arrowstyle='->', lw=2)
        )

        axs[0].set_xlabel('FP time [sec]', fontsize=12)
        axs[0].set_ylabel('Flip minus Blink Time Difference [ms]', fontsize=12)
        axs[0].legend(fontsize=10)
        axs[0].grid(True)
        
        # Plot drift-corrected data and the corrected regression line
        axs[1].plot(df['fp_time_sec'], df['flip_minus_blink_time'] - y_pred, 'o', 
                    label=f'{picam_id}: Flip-Blink Pairs (Drift-corrected)', markersize=2)
        axs[1].plot(df['fp_time_sec'], model.coef_ * df['fp_time_sec'] + model.intercept_ - y_pred, 'k', linewidth=3)
        axs[1].set_xlabel('FP time [sec]', fontsize=12)
        axs[1].set_ylabel('Drift-Corrected Flip minus Blink Time Difference [ms]', fontsize=12)
        axs[1].legend(fontsize=10)
        
        axs[1].axhline(y=-0.015, color="red", linewidth=2, linestyle='--', label='Threshold: -0.015 sec')
        axs[1].axhline(y= 0.015, color="red", linewidth=2, linestyle='--', label='Threshold: 0.015 sec')
        
        axs[1].grid(True)

        # Apply the y-axis scaling to both subplots
        for ax in axs:
            # Get current y-ticks
            yticks = ax.get_yticks()
            # Scale y-ticks to milliseconds
            ax.set_yticks(yticks)  # Explicitly set ticks before applying labels
            ax.set_yticklabels([f'{tick*1000:.0f}' for tick in yticks])
            
        # Set uniform y-axis limits for both subplots
        for ax in axs.flatten():
            ax.set_ylim(-0.05, 0.05)

        # Display the plots
        plt.show()

    return model, df


def find_flip_blink_pairs(df1, df2):
    '''
    finds corresponding pairs of arduino flips (df2, rising and falling) and LED blinks (df1, on/off) and computes 
    the time difference between the two, this time difference can be used to determine drift between 
    the picamera clocks and the FP
    '''

    numpy_df1 = df1.loc[:,'fp_time_sec'].to_numpy() # lag corrected time of the picam LED blinks
    numpy_df2 = df2.loc[:,'fp_time_sec'].to_numpy() # time of the fp flips

    # correct numpy_df1 if picam started earlier than FP or if picam ran longer than FP 
    # (for FP-non-overlapping blinks no valid flip-blink pairs exist and the 
    # find_outliers_regression function doesnt work properly)
    
    # Find the indices where numpy_df1 overlaps with numpy_df2
    start_index = np.searchsorted(numpy_df1, numpy_df2[0] , side='left')
    end_index   = np.searchsorted(numpy_df1, numpy_df2[-1], side='right')
    
    # Create the new numpy_df1 containing only overlapping values
    numpy_df1 = numpy_df1[start_index:end_index+1]

    # Vectorized nearest neighbor search for each blink
    diff_matrix = np.abs(numpy_df1[:, None] - numpy_df2)
    nearest_idx = np.argmin(diff_matrix, axis=1)
    
    picam_fp_pairs = np.vstack((
        nearest_idx, 
        numpy_df2[nearest_idx] - numpy_df1, 
        numpy_df2[nearest_idx]
    )).T
    
    # picam_fp_pairs  = np.empty([len(numpy_df1), 3]) 

    # for ii, value in enumerate(numpy_df1):

    #     idx                    = np.argmin(abs(numpy_df1[ii] - numpy_df2)) # for given blink finds closest flip

    #     picam_fp_pairs[ii, 0]  =  idx
    #     picam_fp_pairs[ii, 1]  =  numpy_df2[idx] - numpy_df1[ii] # time difference between closest flip and blink
        
    #     # picam_fp_pairs[:,2] contains the time of the corresponding flip of a LED blink (on or off) in FP-time 
    #     # minus the time of the first flip, that is necessary because currently the FP is running already 
    #     # when the picams are switching on, this might change in the future!!!
    #     # picam_fp_pairs[ii, 2]  = (numpy_df2[idx] - numpy_df2[picam_fp_pairs[0,0].astype('int')] )/60
    #     picam_fp_pairs[ii, 2]  = numpy_df2[idx]
    
    df3 = pd.DataFrame({'fp_flip_index':         picam_fp_pairs[:, 0].astype('int'), 
                        'flip_minus_blink_time': picam_fp_pairs[:, 1],
                        'fp_time_sec':           picam_fp_pairs[:, 2],
                       })     
    
    return df3
    

def find_outliers_regression(df, picam_id, time_diff_threshold_sec = 0.03):
    '''
    Fits linear function to FP time vs flip-minus-blink time difference.
    Identifies and replaces outliers based on a hardcoded time difference threshold.
    '''
    df2 = df.copy()
    
    x = df2['fp_time_sec'].values.reshape((-1, 1))
    y = df2['flip_minus_blink_time'].values
    
    # Linear regression model for (FP-camera) time difference vs FP time
    model = LinearRegression()
    model.fit(x, y)
    
    residuals = np.abs(y - model.predict(x))  # in seconds
    
    # Outlier threshold (necessary when picamera view of the LED was blocked and no blink was found)
    condition           = residuals > time_diff_threshold_sec 
    outlier_indices     = np.where(condition)[0]
    
    print(f"[{datetime.now():%H:%M:%S}] ({find_outliers_regression.__name__}) "
      f"{len(outlier_indices)} outlier Blink-Flip pairs found and replaced for {picam_id} "
      f"\n{' ' * 38}using a time difference threshold of \u00b1{time_diff_threshold_sec*1000:.2f} msecs!")

    
    # Replace outliers with model prediction
    df2['flip_minus_blink_time'] = np.where(condition, 
                                            model.predict(x), # Replace outliers with predicted value
                                            df2['flip_minus_blink_time']) # Keep original value if not an outlier
    
    return df2, outlier_indices, residuals



def apply_lag_then_drift_picam_correction(df1, lag_picam_sec, drift_model):
    '''
    apply lag first and then drift: 
    fp_time = (picam_time + lag) + a*(picam_time+lag)+b -> fp_time is time of picam_frame in FP timebase
    '''
    
    df2 = df1.copy()
    df2 = apply_lag_picam_correction(df1, lag_picam_sec)
    df2 = apply_drift_picam_correction(df2, drift_model)

    return df2


def apply_lag_picam_correction(df1, lag_picam_sec):
    '''
    takes a signal from the picams (e.g. LED trace or adult_centroid etc) and shifts its time stamps 
    ('frame_time_sec') by the time lag between the LED trace and arduino_voltage 
    as determined by resample_xcorr()
    '''
    
    df2                = df1.copy()
    df2['fp_time_sec'] = df1['frame_time_sec'] + lag_picam_sec
    
    return df2
    
    
def apply_drift_picam_correction(df, drift_model):
    '''
    (fp_flip_time - picam_blink_time) = a*fp_time + b
    picam_blink_time = fp_flip_time - (a*fp_time + b)
    -> compensating for the picam drift with respect to fp_time (i.e. that fp_flip_time = picam_blink_time) 
    results in: compensated_picam_time = old_picam_time + (a*fp_time + b)
    '''
    df1                = df.copy() 
    df1['fp_time_sec'] = df['fp_time_sec'] + (drift_model.coef_ * df['fp_time_sec'] + drift_model.intercept_)

    return df1


def find_closest_picam_frame(fp_time_sec, picam_LEDsignal_drft_corr):
    
    # Calculate the absolute differences between the given fp_time_sec and all values in 'fp_time_sec' column
    diff = np.abs(picam_LEDsignal_drft_corr['fp_time_sec'] - fp_time_sec)
    
    # Find the index of the minimum difference (closest match)
    closest_index = diff.idxmin()
   
    return closest_index

def map_fp_time_to_picam_frames(opto_pulse_train_timing, picam_id, picam_LEDsignal_drft_corr):

    # Create an empty list to store the new rows (start and end frames)
    result = []
    
    # Loop through each row in stim_times_df
    for _, row in opto_pulse_train_timing.iterrows():
        # Find the closest picam frame for start_stim_fp_sec
        start_frame = find_closest_picam_frame(row['start_stim_fp_sec'], picam_LEDsignal_drft_corr)
        # Find the closest picam frame for end_stim_fp_sec
        end_frame   = find_closest_picam_frame(row['end_stim_fp_sec'], picam_LEDsignal_drft_corr)
        
        # Append the results to the list
        result.append({
            'start_stim_fp_sec': row['start_stim_fp_sec'],
            'end_stim_fp_sec': row['end_stim_fp_sec'],
            f'start_stim_{picam_id}_frame': start_frame,
            f'end_stim_{picam_id}_frame': end_frame
        })
    
    # Convert the list of results into a DataFrame
    opto_pulse_train_timing = pd.DataFrame(result, index=pd.Index(range(len(result)), name='pulse_train_index'))
    
    return opto_pulse_train_timing


def plot_picam_FP_sync_data(homedir, expID, picam_dict, fp_dict, sync_dict, xmin, xmax):
    
    arduino_voltage      = fp_dict['fp_timing']['arduino_voltage']
    arduino2fp_flips     = fp_dict['fp_timing']['digital_IOs']['Input0']
    
    picam_list           = find_picams(homedir, expID)
    picam_blink_marker   = ['s', 'x']
    
    fig, axs = plt.subplots(nrows = 1, ncols = 1, figsize = (15,8), constrained_layout=True)
    fig.suptitle('Experiment ID: ' + expID, fontsize = 20) 
    
    axs.plot(arduino_voltage['fp_time_sec'], arduino_voltage['voltage'], 
            linewidth=2, 
            label = 'reconstructed LED voltage'
           );    
    axs.plot(arduino2fp_flips['fp_time_sec'], arduino2fp_flips['edge'],
            'ro', 
            markersize=10, 
            markerfacecolor='none',
            label = 'edge timestamps'
           );   

    axs.tick_params(axis='both', which='major', labelsize=15)
    axs.set_xlim(xmin, xmax)
    axs.set_ylim(-0.5,  11)
    axs.set_xlabel('fp time in sec', fontsize=19)
    axs.set_ylabel('normalized LED intensity and voltage in a.u.', fontsize=19)
    axs.legend(fontsize=11, loc='upper right')
    
    for idx, picam_id in enumerate(picam_list):
        
      #  picam_LED             = picam_dict[picam_id]['picam_timing']['picam_LEDsignal']
      #  picam_LED_blinks      = picam_dict[picam_id]['picam_timing']['picam_LED_blinks']
        picam_LED_corr        = sync_dict[picam_id]['picam_LEDsignal_drft_corr']
        picam_LED_blinks_corr = sync_dict[picam_id]['picam_LED_blinks_drft_corr']
        
        axs.plot(picam_LED_corr['fp_time_sec'], picam_LED_corr['LED_ROI_avg'] + 3.5*idx+2.5,
                    label = picam_id + ': normalized LED ROI average, aligned & drift corrected')
        axs.plot(picam_LED_blinks_corr['fp_time_sec'], picam_LED_blinks_corr['blinks']   + 3.5*idx+2.5,
                    'k',
                    markersize = 8, 
                    marker = picam_blink_marker[idx],
                    linestyle = '',
                    label = picam_id + ': on/off blinks, aligned & drift-corrected'
                   ); 
        axs.legend(fontsize=11, loc='upper right')
        
    return


def resample_FP_signal_to_picam_time(fp, signal, sync_dict, picam_id):
    ''' Resamples timestamps of the normalized FP-derived signal to the synced picamera timestamps '''
    time_vector = fp.loc[:, 'fp_time_sec'].to_numpy()
    data_points = fp.loc[:, signal].to_numpy()
    time_vector_interp = sync_dict[picam_id]['picam_LEDsignal_drft_corr'].loc[:, 'fp_time_sec'].to_numpy()
    data_points_interp = np.interp(time_vector_interp, time_vector, data_points)
    return time_vector_interp, data_points_interp

def set_plot_style(ax, fibers, fiber):
    '''
    Set the style for each plot (title, labels, etc.).
    '''
    ax.set_facecolor('black')
    ax.set_ylim(-5, 12)
    
    # Customize axis labels and spines
    ax.xaxis.label.set_color('white')
    ax.yaxis.label.set_color('white')
    ax.spines['bottom'].set_color('white')
    ax.spines['left'].set_color('white')
    ax.spines['bottom'].set_linewidth(3)
    ax.spines['left'].set_linewidth(3)

    # Customize tick marks appearance
    ax.tick_params(direction='out', length=6, width=3, colors='white')
    plt.setp(ax.get_xticklabels(), fontsize=14)
    plt.setp(ax.get_yticklabels(), fontsize=14)
    
    # Set graph title and axis labels
    ax.set_title(fiber, fontsize=20, color='white', pad=10, loc='left', x=0.05)

    if fiber == fibers[-1]:
        ax.set_xlabel('time in sec', fontsize=16)
    ax.set_ylabel('zF/F', fontsize=16)


def initialize_lines_and_text(ax):
    ''' Initialize plot lines and text for dynamic updates '''
    line1, = ax.plot([], [], '-', color = 'white'  , lw=3)
    line2, = ax.plot([], [], '-', color = 'cyan', lw=2)
    vl = ax.axvline(0, ls='-', color='red', lw=3)
    
    txt1 = ax.text(0, 0, '', color='red', fontsize=16)
    txt2 = ax.text(0, 0, '', color='white', fontsize=16)
    txt3 = ax.text(0, 0, '', color='white', fontsize=16)
    
    return line1, line2, vl, txt1, txt2, txt3


def generate_FP_signal_picam_video(homedir, expID, fp_dict, picam_dict, sync_dict, 
                                   picam_id, fibers, window_sec=15, display_video=False):
    '''
    Generates a synced FP signal video with overlaid graphs placed in a single column of subplots.
    '''
    folder = os.path.join(homedir, expID, '01_picams', '02_conv')  
    pattern = os.path.join(folder, f"{expID}_{picam_id}.mp4")  
    
    input_video = cv2.VideoCapture(glob.glob(pattern)[0])
    
    if not os.path.isfile(pattern):
        print(f'[{datetime.now().strftime("%H:%M:%S")}] Video file not found!')
        return

    if os.path.exists(f'{os.path.splitext(pattern)[0]}_graph.mp4'):
        print(f'[{datetime.now():%H:%M:%S}] Synced FP video for {picam_id} and {expID} already exists! Aborting...')
        return
    
    print(f'\n[{datetime.now():%H:%M:%S}] Creating synced FP video for {picam_id} of experiment {expID}...')
    
    # Initialize video and graph parameters
    video_width               = int(input_video.get(3))
    video_height              = int(input_video.get(4))
    graph_width, graph_height = 350, 350  # Graph dimensions
    num_graphs                = len(fibers)

    output_video = cv2.VideoWriter(
        os.path.join(folder, f'{expID}_{picam_id}_graph.mp4'),
        cv2.VideoWriter_fourcc(*'mp4v'), 
        input_video.get(cv2.CAP_PROP_FPS), 
        (video_width + graph_width, video_height)
    )

    picam_fps    = picam_dict[picam_id]['picam_metadata']['fps']
    window       = int(picam_fps * window_sec / 2)
    total_frames = int(input_video.get(cv2.CAP_PROP_FRAME_COUNT))

    # Load and resample FP signal data to picam time
    df2 = fp_dict['fp_timing']['arduino_voltage']
    signal = 'voltage'
    x2, y2 = resample_FP_signal_to_picam_time(df2, signal, sync_dict, picam_id)

    # Initialize figure for graphs
    fig, axes = plt.subplots(nrows=num_graphs, ncols=1, figsize=(7, num_graphs * 5), sharex=True, sharey=True)
    fig.patch.set_facecolor('black')  # Set figure background color to black

    lines1, lines2, vls, texts, x1s, y1s = [], [], [], [], [], []
    
    for ii, fiber in enumerate(fibers):
        ax = axes[ii]  
        set_plot_style(ax, fibers, fiber)
        
        line1, line2, vl, txt1, txt2, txt3 = initialize_lines_and_text(ax)
        lines1.append(line1)
        lines2.append(line2)
        vls.append(vl)
        texts.append((txt1, txt2, txt3))

        # Resample FP signal data for the current fiber
        signal = f'{fiber}_zDF/F'
        x1, y1 = resample_FP_signal_to_picam_time(fp_dict['fp_fluorescence']['fp_normalized_data'], signal, sync_dict, picam_id)
        x1s.append(x1)
        y1s.append(y1)

    frame_num = 0
    with tqdm(total=total_frames) as pbar:
        while True:
            success, frame = input_video.read()
            if not success:
                break

            # Create a new black frame larger than the original video
            new_frame = np.zeros((video_height, video_width + graph_width, 3), dtype=np.uint8)

            # Update graphs for each fiber
            for i, (x1, y1, vl, line1, line2, txt1, txt2, txt3, ax) in enumerate(zip(x1s, y1s, vls, lines1, lines2, *zip(*texts), axes)):
                line1.set_xdata(x1[:frame_num + window])
                line1.set_ydata(y1[:frame_num + window])
                line2.set_xdata(x2[:frame_num + window])
                line2.set_ydata(y2[:frame_num + window] - 4)
                vl.set_xdata([x1[frame_num]])

                # Update text annotations
                txt1.set_position([x1[frame_num] + 1.5, 0.90 * ax.get_ylim()[1]])
                txt1.set_text(f'time = {x1[frame_num]:.3f}')
                txt2.set_position([x1[frame_num] + 1.5, 0.80 * ax.get_ylim()[1]])
                txt2.set_text(f'zF/F = {y1[frame_num]:.3f}')
                txt3.set_position([x1[frame_num] + 1.5, 0.70 * ax.get_ylim()[1]])
                txt3.set_text(f'LED = {y2[frame_num]:.1f}')

                # Adjust xlim based on frame_num
                ax.set_xlim((2 * x1[frame_num] - x1[frame_num + window], x1[frame_num + window]) 
                            if frame_num <= total_frames - window - 1 
                            else (x1[frame_num - window], 2 * x1[frame_num] - x1[frame_num - window]))

            # Convert figure to OpenCV image
            fig.canvas.draw()
            graph         = np.array(fig.canvas.get_renderer()._renderer)
            graph         = cv2.cvtColor(graph, cv2.COLOR_RGB2BGR)
            resized_graph = cv2.resize(graph, (graph_width, graph_height * num_graphs))

            # Place the video frame and graph into the new frame
            new_frame[:video_height, :video_width] = frame
            new_frame[:graph_height * num_graphs, video_width:] = resized_graph


            if 'OptoStimulation' in fp_dict['fp_metadata']:
            
                stim_timings   = sync_dict[picam_id]['opto_pulse_train_timing']
                stim_start_col = f'start_stim_{picam_id}_frame'
                stim_end_col   = f'end_stim_{picam_id}_frame'
                
                # Check if current frame number (zero-based) falls within any of the stimulation windows
                stim_active = any(
                    (start <= frame_num <= end)
                    for start, end in zip(stim_timings[stim_start_col], stim_timings[stim_end_col])
                )
                
                # If stimulation is active in a frame, draw magenta circle
                if stim_active:
                    circle_center = (video_width+45, video_height-35)  # lower right corner
                    cv2.circle(new_frame, circle_center, 30, (255, 0, 255), -1)  # Magenta color (255, 0, 255), filled circle

            
            # Write the new frame with the graph to the output video
            output_video.write(new_frame)

            if display_video:
                cv2.imshow('frame', new_frame)
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    break

            frame_num += 1
            pbar.update(1)

    input_video.release()
    output_video.release()
    cv2.destroyAllWindows()

    print(f'[{datetime.now().strftime("%H:%M:%S")}] Creating synced FP video...Done!')









# MISC functions

def print_dict(d, indent=0):
    '''
    prints key structure of dictionary 
    '''

    for key, value in d.items():
      print('\t' * indent + str(key))
      if isinstance(value, dict):
         print_dict(value, indent+1)
      else:
         print('\t' * (indent+1) )

# def load_pickle_file(homedir, expID):
#     '''Helper function to load a pickle file, return None if not found'''
    
#     pickle_folder   = homedir + expID + '/04_pickle_snapshots/'
#     pickle_filepath = pickle_folder + expID + '_sync_dict.pickle'
    
#     if os.path.exists(pickle_filepath):
#         with open(pickle_filepath, 'rb') as f:
#             return pickle.load(f)
#     return None


# def save_as_pickle(source_dict, filepath):
#     '''
#     saves source dictionary as pickle file
#     '''
#     with open(filepath, 'wb') as file_handle:
#         pickle.dump(source_dict, file_handle, protocol=pickle.HIGHEST_PROTOCOL)

def load_sync_pickle_file(homedir, expID):
    """
    Loads a pickle file for the given experiment, if it exists.
    """
    pickle_filepath = os.path.join(homedir, expID, '04_pickle_snapshots', f'{expID}_sync_dict.pickle')
    
    if os.path.exists(pickle_filepath):
        with open(pickle_filepath, 'rb') as f:
            return pickle.load(f)
    
    return None


def save_sync_pickle_file(homedir, expID, sync_dict):
    """
    Saves the given dictionary as a pickle file.

    Args:
        homedir (str): Base directory for the experiment.
        expID (str): Experiment ID.
        sync_dict (dict): Dictionary to save.
    """
    function_name = inspect.currentframe().f_code.co_name

    pickle_folder = os.path.join(homedir, expID, '04_pickle_snapshots')
    pickle_filepath = os.path.join(pickle_folder, f'{expID}_sync_dict.pickle')

    os.makedirs(pickle_folder, exist_ok=True)

    # Handle existing file
    if os.path.exists(pickle_filepath):
        existing_dict = load_sync_pickle_file(homedir, expID)
        if existing_dict:
            existing_status = existing_dict.get('sync_PICAM_FP_run', None)
            new_status = sync_dict.get('sync_PICAM_FP_run', None)

            if existing_status is False and new_status is True:
                print(f"\n[{datetime.now():%H:%M:%S}] ({function_name}) Overwriting existing sync_dict.pickle file because 'sync_PICAM_FP_run' is False in the existing file and True in the sync_dict.pickle file.")
            else:
                print(f"\n[{datetime.now():%H:%M:%S}] ({function_name}) File already exists. Saving aborted.")
                return

    # Save the new file
    with open(pickle_filepath, 'wb') as f:
        pickle.dump(sync_dict, f, protocol=pickle.HIGHEST_PROTOCOL)

    print(f'\n[{datetime.now():%H:%M:%S}] ({function_name}) Synchronized PICAM-FP Data saved as pickle file!')


