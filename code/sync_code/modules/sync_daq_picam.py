# Standard Library Imports
import os
import re
import glob
import inspect
from datetime import datetime
from pathlib import Path

# Third-Party Libraries
import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression
import matplotlib.pyplot as plt

def synchronize_daq_picameras(datadir, expID, picam_dict, daq_dict, verbose=False):
    '''
    Main function for synchronizing two picameras (slaves) with the Fiber photometry system (master).
    Input are the two dictionaries (for DAQ and the PiCameras) which contain the Arduino edges and the LED blinks.
    '''
    function_name = inspect.currentframe().f_code.co_name

    print('\n-------------------------------------------------------------------------------------------------------------')
    print(f'\n[{datetime.now():%H:%M:%S}] ({function_name}) Synchronizing DAQ and PiCamera data for experiment {expID}\n                                   using ROI intensity-voltage matching of the same blinking LED.')

    sync_dict = initialize_sync_dict(datadir, expID, picam_dict, daq_dict, verbose)

    # Print sync summary stats
    print(f'\n[{datetime.now():%H:%M:%S}] ({function_name}) PICAMERA-DAQ synchronization SUMMARY:\n')

    for picam_id in sync_dict['picam_list']:
        print(f'            {picam_id}-DAQ lag (sec): {sync_dict[picam_id]["lag_picam_sec"] - daq_dict["daq_timing"]["arduino_voltage_df"].iloc[0, 0]:.4f}')

    if sync_dict['picam_list'] == ['pic1', 'pic2']:
        print(f'            lagPicam1-lagPicam2 (sec): '
              f'{sync_dict["pic1"]["lag_picam_sec"] - sync_dict["pic2"]["lag_picam_sec"]:.4f}')
 
    return sync_dict

def initialize_sync_dict(datadir, expID, picam_dict, daq_dict, verbose):
    '''
    Initializes the sync_dict by performing synchronization of DAQ and picam data.
    '''
    function_name = inspect.currentframe().f_code.co_name

    sync_dict = {
        'expID': expID,
        'sync_data_save_datetime': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        'picam_list': [],
        'PICAM_DAQ_sync_run': False
    }

    arduino_voltage   = daq_dict['daq_timing']['arduino_voltage_df'].copy()
    arduino2daq_edges = daq_dict['daq_timing']['arduino2daq_edges_df'].copy()

    picam_list = find_picams(datadir, expID)
    sync_dict['picam_list'] = picam_list

    for picam_id in picam_list:
        sync_dict[picam_id] = {}

        picam_LEDsignal = picam_dict[picam_id]['picam_timing']['picam_LEDsignal'].copy()
        picam_LED_blinks = picam_dict[picam_id]['picam_timing']['picam_LED_blinks'].copy()

        print(f"\n[{datetime.now():%H:%M:%S}] ({function_name}) Calculate lag between DAQ signal and {picam_id} using cross-correlation.")
        lag_picam_sec = calculate_lag_xcorr(picam_LEDsignal, arduino_voltage, new_timebase_s=0.01)

        model_picam, _ = determine_picam_daq_drift_and_plot(picam_LED_blinks, arduino2daq_edges, lag_picam_sec, picam_id, verbose)

        picam_LEDsignal_drft_corr = apply_lag_then_drift_picam_correction(picam_LEDsignal, lag_picam_sec, model_picam)
        picam_LED_blinks_drft_corr = apply_lag_then_drift_picam_correction(picam_LED_blinks, lag_picam_sec, model_picam)

        sync_dict[picam_id]['lag_picam_sec']              = lag_picam_sec
        sync_dict[picam_id]['model_parameters']           = [model_picam.coef_[0], model_picam.intercept_]
        sync_dict[picam_id]['picam_LEDsignal_drft_corr']  = picam_LEDsignal_drft_corr
        sync_dict[picam_id]['picam_LED_blinks_drft_corr'] = picam_LED_blinks_drft_corr
        
    sync_dict['PICAM_DAQ_sync_run'] = True

    return sync_dict


def find_picams(datadir, expID):
    '''
    Finds unique picam modifiers (pic1, pic2, ...) in the working folder.
    Only processes .txt files.
    '''
    function_name = inspect.currentframe().f_code.co_name
    
    folder = os.path.join(datadir, expID, '01_picams', '01_raw')

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
    df2_resampled = resample_signal(df2,    'daq_time_sec', 'voltage',     new_timebase_s)
    
    lag_picam_sec, _ = xcorr(df1_resampled, df2_resampled)
    lag_picam_sec   += df1['frame_time_sec'].iloc[0]  # Add the first timestamp from df1 to the lag

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
    time_df2, y = df2['daq_time_sec'].to_numpy(), df2['voltage'].to_numpy()

    # Perform cross-correlation
    corrCoeff = np.correlate(y, x, 'full')
    lagsOut   = np.arange(-len(x), len(y)-1)

    # Find the lag corresponding to the maximum correlation coefficient
    lag         = lagsOut[np.argmax(corrCoeff)]
    lag_pic_sec = time_df2[lag]

    return lag_pic_sec, df1


def determine_picam_daq_drift_and_plot(df1, df2, lag_picam_sec, picam_id, verbose=True):
    '''
    Determines the drift between the picamera time and DAQ time after applying a lag correction.
    This function fits a linear regression model to the time difference between picam LED blinks 
    and DAQ edges, corrects for any drift, and plots the results.

    Parameters:
        df1 (pd.DataFrame): DataFrame containing picam LED blink data. Must include 'daq_time_sec' 
                           (DAQ time) and 'edge_minus_blink_time' (time difference between edge and blink).
        df2 (pd.DataFrame): DataFrame containing DAQ edge data. Must include 'daq_time_sec' (DAQ time).
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
    
    # Step 2: Find DAQ-edge-LED-blink pairs
    df = find_edge_blink_pairs(df1, df2)
    print(f"[{datetime.now():%H:%M:%S}] ({function_name}) {len(df)} Edge-Blink pairs found for {picam_id}.")
    
    # Step 3: Find and remove outliers by fitting a linear curve and then replace the outliers by their predicted value
    time_diff_threshold_sec = 0.03
    df, _, _ = find_outliers_regression(df, picam_id, time_diff_threshold_sec)
    
    # Step 4: Prepare data for linear regression model
    x = df['daq_time_sec'].values.reshape((-1, 1))  # Independent variable (DAQ time)
    y = df['edge_minus_blink_time'].values  # Dependent variable (time difference between edge and blink)
    
    # Step 5: Fit another linear model of (DAQ-picamera) time difference vs. DAQ time this time with corrected outliers
    model = LinearRegression()
    model.fit(x, y)
    
    # Step 6: Predict the time difference based on the model
    y_pred = model.predict(x)
    
    if verbose:
        function_name = inspect.currentframe().f_code.co_name
        
        # Print model coefficients
        print(f"\n[{datetime.now():%H:%M:%S}] ({function_name}) {picam_id:} slope:     {model.coef_[0]:.6f}\n"
              f"{' ' * 48}{picam_id:} intercept:  {model.intercept_:.6f}\n")

        # Step 7: Plotting the results
        # Create a figure and axes for two subplots
        fig, axs = plt.subplots(nrows=1, ncols=2, figsize=(12, 5), constrained_layout=True)
        
        # Plot raw data and the regression line
        axs[0].plot(df['daq_time_sec'], df['edge_minus_blink_time'], 'o', label=f'{picam_id}: Edge-Blink Pairs', markersize=2, color='tab:blue')
        axs[0].plot(df['daq_time_sec'], model.coef_ * df['daq_time_sec'] + model.intercept_, 'k', linewidth=3)
        
        # Add grey horizontal line at y=0 (highest zorder, at the front)
        axs[0].axhline(y=0, color='grey', linewidth=2, linestyle='-', zorder=5)
        
        # Add textbox in the lower left corner of axs[0]
        # Compute the x-coordinate where the regression line intersects y=0
        
        intersection_time = -model.intercept_ / model.coef_[0]  # Solve model.coef_ * x + model.intercept_ = 0
        
        # Add a multi-line textbox in the lower left corner of axs[0]
        textbox_text = (
            f'Above y=0 (the grey line), the {picam_id} signal was acquired faster \nthan the DAQ signal and slower below the grey line.\n\nReversal timepoint: {intersection_time:.1f} sec'
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

        axs[0].set_xlabel('DAQ time [sec]', fontsize=12)
        axs[0].set_ylabel('Edge minus Blink Time Difference [ms]', fontsize=12)
        axs[0].legend(fontsize=10)
        axs[0].grid(True)
        
        # Plot drift-corrected data and the corrected regression line
        axs[1].plot(df['daq_time_sec'], df['edge_minus_blink_time'] - y_pred, 'o', 
                    label=f'{picam_id}: Edge-Blink Pairs (Drift-corrected)', markersize=2)
        axs[1].plot(df['daq_time_sec'], model.coef_ * df['daq_time_sec'] + model.intercept_ - y_pred, 'k', linewidth=3)
        axs[1].set_xlabel('DAQ time [sec]', fontsize=12)
        axs[1].set_ylabel('Drift-Corrected Edge minus Blink Time Difference [ms]', fontsize=12)
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


def find_edge_blink_pairs(df1, df2):
    '''
    finds corresponding pairs of arduino edges (df2, rising and falling) and LED blinks (df1, on/off) and computes 
    the time difference between the two, this time difference can be used to determine drift between 
    the PiCamera clocks and the DAQ
    '''

    numpy_df1 = df1.loc[:,'daq_time_sec'].to_numpy() # lag corrected time of the PiCamera LED blinks
    numpy_df2 = df2.loc[:,'daq_time_sec'].to_numpy() # time of the DAQ edges

    # correct numpy_df1 if picam started earlier than DAQ or if PiCamera ran longer than DAQ 
    # (for DAQ-non-overlapping blinks no valid Edge-Blink pairs exist and the 
    # find_outliers_regression function doesnt work properly)
    
    # Find the indices where numpy_df1 overlaps with numpy_df2
    start_index = np.searchsorted(numpy_df1, numpy_df2[0] , side='left')
    end_index   = np.searchsorted(numpy_df1, numpy_df2[-1], side='right')
    
    # Create the new numpy_df1 containing only overlapping values
    numpy_df1 = numpy_df1[start_index:end_index+1]

    # Vectorized nearest neighbor search for each blink
    diff_matrix = np.abs(numpy_df1[:, None] - numpy_df2)
    nearest_idx = np.argmin(diff_matrix, axis=1)
    
    picam_daq_pairs = np.vstack((
        nearest_idx, 
        numpy_df2[nearest_idx] - numpy_df1, 
        numpy_df2[nearest_idx]
    )).T
    
    df3 = pd.DataFrame({'daq_edge_index':         picam_daq_pairs[:, 0].astype('int'), 
                        'edge_minus_blink_time': picam_daq_pairs[:, 1],
                        'daq_time_sec':           picam_daq_pairs[:, 2],
                       })     
    
    return df3
    

def find_outliers_regression(df, picam_id, time_diff_threshold_sec = 0.03):
    '''
    Fits linear function to DAQ time vs edge-minus-blink time difference.
    Identifies and replaces outliers based on a hardcoded time difference threshold.
    '''
    df2 = df.copy()
    
    x = df2['daq_time_sec'].values.reshape((-1, 1))
    y = df2['edge_minus_blink_time'].values
    
    # Linear regression model for (DAQ-picamera) time difference vs DAQ time
    model = LinearRegression()
    model.fit(x, y)
    
    residuals = np.abs(y - model.predict(x))  # in seconds
    
    # Outlier threshold (necessary when picamera view of the LED was blocked and no blink was found)
    condition           = residuals > time_diff_threshold_sec 
    outlier_indices     = np.where(condition)[0]
    
    print(f"[{datetime.now():%H:%M:%S}] ({find_outliers_regression.__name__}) "
      f"{len(outlier_indices)} outlier Edge-Blink pairs found and replaced for {picam_id} "
      f"\n{' ' * 38}using a time difference threshold of \u00b1{time_diff_threshold_sec*1000:.2f} msecs!")

    # Replace outliers with model prediction
    df2['edge_minus_blink_time'] = np.where(condition, 
                                            model.predict(x), # Replace outliers with predicted value
                                            df2['edge_minus_blink_time']) # Keep original value if not an outlier
    
    return df2, outlier_indices, residuals


def apply_lag_then_drift_picam_correction(df1, lag_picam_sec, drift_model):
    '''
    apply lag first and then drift: 
    daq_time = (picam_time + lag) + a*(picam_time+lag)+b -> daq_time is time of picam_frame in DAQ timebase
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
    df2['daq_time_sec'] = df1['frame_time_sec'] + lag_picam_sec
    
    return df2
    
    
def apply_drift_picam_correction(df, drift_model):
    '''
    (daq_edge_time - picam_blink_time) = a*daq_time + b
    picam_blink_time = daq_edge_time - (a*daq_time + b)
    -> compensating for the picam drift with respect to daq_time (i.e. that daq_edge_time = picam_blink_time) 
    results in: compensated_picam_time = old_picam_time + (a*daq_time + b)
    '''
    df1                 = df.copy() 
    df1['daq_time_sec'] = df['daq_time_sec'] + (drift_model.coef_ * df['daq_time_sec'] + drift_model.intercept_)

    return df1


def find_closest_picam_frame(daq_time_sec, picam_LEDsignal_drft_corr):
    
    # Calculate the absolute differences between the given daq_time_sec and all values in 'daq_time_sec' column
    diff = np.abs(picam_LEDsignal_drft_corr['daq_time_sec'] - daq_time_sec)
    
    # Find the index of the minimum difference (closest match)
    closest_index = diff.idxmin()
   
    return closest_index


def plot_picam_daq_sync_data(datadir, expID, picam_dict, daq_dict, sync_dict, xmin, xmax):
    """
    Description:
    This function visualizes the synchronization of PiCamera recordings with DAQ (Data Acquisition) system timestamps 
    using LED blinking as a reference. It plots the Arduino-controlled LED voltage recorded by the DAQ, 
    detected edges (on/off transitions), and the extracted LED intensity from PiCamera recordings.
    
    Parameters:
    - datadir (str): Directory containing experiment data.
    - expID (str): Unique identifier for the experiment.
    - picam_dict (dict): Dictionary containing PiCamera metadata.
    - daq_dict (dict): Dictionary containing DAQ system timing and recorded signals.
    - sync_dict (dict): Dictionary containing synchronization results, including drift-corrected LED signals.
    - xmin (float): Minimum x-axis limit (DAQ time in seconds).
    - xmax (float): Maximum x-axis limit (DAQ time in seconds).
    
    Plot Details:
    - The DAQ-recorded Arduino LED voltage is plotted as a continuous line.
    - Detected edge timestamps from the DAQ are marked with red circles.
    - Each PiCamera’s extracted LED signal (drift-corrected) is plotted with an offset for clarity.
    - Detected blinks in each PiCamera’s signal are marked with distinct symbols.
    
    Returns:
    - None (displays the plot).
    
    """

    arduino_voltage    = daq_dict['daq_timing']['arduino_voltage_df']
    arduino2daq_edges  = daq_dict['daq_timing']['arduino2daq_edges_df']
    
    picam_list         = find_picams(datadir, expID)
    picam_blink_marker = ['s', 'x']
    
    fig, axs = plt.subplots(nrows = 1, ncols = 1, figsize = (15,8), constrained_layout=True)
    fig.suptitle('Experiment ID: ' + expID, fontsize = 20) 
    
    axs.plot(arduino_voltage['daq_time_sec'], arduino_voltage['voltage'], 
            linewidth=2, 
            label = 'arduino LED voltage'
           );    
    axs.plot(arduino2daq_edges['daq_time_sec'], arduino2daq_edges['edges'],
            'ro', 
            markersize=10, 
            markerfacecolor='none',
            label = 'edge timestamps'
           );   

    axs.tick_params(axis='both', which='major', labelsize=15)
    axs.set_xlim(xmin, xmax)
    axs.set_ylim(-0.5,  11)
    axs.set_xlabel('daq time in sec', fontsize=19)
    axs.set_ylabel('normalized LED intensity and voltage in a.u.', fontsize=19)
    axs.legend(fontsize=11, loc='upper right')
    
    for idx, picam_id in enumerate(picam_list):
        
        picam_LED_corr        = sync_dict[picam_id]['picam_LEDsignal_drft_corr']
        picam_LED_blinks_corr = sync_dict[picam_id]['picam_LED_blinks_drft_corr']
        
        axs.plot(picam_LED_corr['daq_time_sec'], picam_LED_corr['LED_ROI_avg'] + 3.5*idx+2.5,
                    label = picam_id + ': normalized LED ROI average, aligned & drift corrected')
        axs.plot(picam_LED_blinks_corr['daq_time_sec'], picam_LED_blinks_corr['blinks']   + 3.5*idx+2.5,
                    'k',
                    markersize = 8, 
                    marker = picam_blink_marker[idx],
                    linestyle = '',
                    label = picam_id + ': on/off blinks, aligned & drift-corrected'
                   ); 
        axs.legend(fontsize=11, loc='upper right')
        
    return


def plot_picam_daq_sync_data(datadir, expID, picam_dict, daq_dict, sync_dict):
    """
    Plots synchronized data from PiCameras and DAQ recordings.

    This function creates a figure with two subplots displaying the Arduino LED voltage,
    detected edge timestamps, and processed LED signals from PiCameras. The subplots
    show two time intervals: one centered around the first detected LED signal and the
    other around the last detected LED signal.

    Parameters:
    datadir (str): Path to the data directory.
    expID (str): Experiment identifier.
    picam_dict (dict): Dictionary containing PiCamera data.
    daq_dict (dict): Dictionary containing DAQ timing and voltage data.
    sync_dict (dict): Dictionary containing synchronization data for PiCameras.

    Returns:
    None: The function generates and displays the plots.
    """
    arduino_voltage    = daq_dict['daq_timing']['arduino_voltage_df']
    arduino2daq_edges  = daq_dict['daq_timing']['arduino2daq_edges_df']
    
    picam_list         = find_picams(datadir, expID)
    picam_blink_marker = ['s', 'x']
    
    fig, axs = plt.subplots(nrows=1, ncols=2, figsize=(20,8), constrained_layout=True)
    fig.suptitle('Experiment ID: ' + expID, fontsize=20)
    
    for idx, picam_id in enumerate(picam_list):
        picam_LED_corr        = sync_dict[picam_id]['picam_LEDsignal_drft_corr']
        picam_LED_blinks_corr = sync_dict[picam_id]['picam_LED_blinks_drft_corr']
        
        xlim1_min = picam_LED_corr['daq_time_sec'].iloc[0] - 10
        xlim1_max = picam_LED_corr['daq_time_sec'].iloc[0] + 10
        xlim2_min = picam_LED_corr['daq_time_sec'].iloc[-1] - 10
        xlim2_max = picam_LED_corr['daq_time_sec'].iloc[-1] + 10
        
        for ax, xmin, xmax in zip(axs, [xlim1_min, xlim2_min], [xlim1_max, xlim2_max]):
            ax.plot(arduino_voltage['daq_time_sec'], arduino_voltage['voltage'], linewidth=2, label='arduino LED voltage')
            ax.plot(arduino2daq_edges['daq_time_sec'], arduino2daq_edges['edges'], 'ro', markersize=10, markerfacecolor='none', label='edge timestamps')
            
            ax.plot(picam_LED_corr['daq_time_sec'], picam_LED_corr['LED_ROI_avg'] + 3.5*idx+2.5, label=picam_id + ': normalized LED ROI average, aligned & drift corrected')
            ax.plot(picam_LED_blinks_corr['daq_time_sec'], picam_LED_blinks_corr['blinks'] + 3.5*idx+2.5, 'k', markersize=8, marker=picam_blink_marker[idx], linestyle='', label=picam_id + ': on/off blinks, aligned & drift-corrected')
            
            ax.tick_params(axis='both', which='major', labelsize=15)
            ax.set_xlim(xmin, xmax)
            ax.set_ylim(-0.5, 11)
            ax.set_xlabel('daq time in sec', fontsize=19)
            ax.set_ylabel('normalized LED intensity and voltage in a.u.', fontsize=19)
            ax.legend(fontsize=11, loc='upper right')
    
    return
