import numpy as np
import pandas as pd
import re
import matplotlib.pyplot as plt
from datetime import datetime
import inspect
from scipy.stats import zscore
from scipy import optimize
from sklearn.linear_model import LinearRegression
from scipy.signal import filtfilt, find_peaks
from scipy.sparse import diags, csc_matrix, eye
from scipy.sparse.linalg import spsolve
from scipy import optimize


def analyze_fp_time(fp_dict, verbose=False):
    """
    Extracts and analyzes FP timestamps from fp_full_data.csv.
    Identifies dropped frames and plots the interframe intervals if verbose is True.
    Adds a flag 'fp_frame_analysis_run' to ensure the analysis is performed only once.

    Args:
        fp_dict (dict): Dictionary containing the experiment data, including 'fp_fluorescence' with 'fp_interleaved_data' (DataFrame with frame info) and 'fp_metadata'.
        verbose (bool): If True, additional plots are generated.

    Returns:
        dict: Updated fp_dict with analysis results and 'fp_frame_analysis_run' flag set.
    """
    function_name = inspect.currentframe().f_code.co_name
    
    exp = fp_dict['expID']
    
    # Check if the analysis has already been run
    if fp_dict.get('fp_frame_analysis_run', True):
        print(f"[{datetime.now():%H:%M:%S}] ({function_name}) Frame analysis already completed for experiment {exp}. Skipping reanalysis.")
        return fp_dict
    
    print(f"\n\n[{datetime.now():%H:%M:%S}] ({function_name}) Analyzing FP frame times for experiment {exp}:")
    
    # Extract data from fp_dict
    fp_time = fp_dict['fp_timing']['fp_frame_info']
    fps = int(fp_dict['fp_metadata']['Excitation']['TriggerPeriod_Hz'])
    
    # Preprocess frame data
    fp_time = preprocess_fp_data(fp_time)

    # Identify dropped frames and return the indices and count
    dropped_frames_indices, dropped_frames_count = identify_dropped_FP_frames(fp_time)

    # Create a DataFrame for dropped frames
    dropped_frames_df = create_dropped_FP_frames_dataframe(fp_time, dropped_frames_indices, dropped_frames_count)

    # Print the results
    total_frames = len(fp_time.index)
    total_dropped = int(np.sum(dropped_frames_count.to_numpy()))

    print(f"\nFrame analysis for FP:")
    print(f"   Total number of FP frames found: {total_frames}")
    print(f"   Total number of dropped FP frames: {total_dropped}")

    if verbose:
        plot_FP_frame_intervals(fp_time, dropped_frames_df)

    # Analyze Arduino LED TTL signals
    analyze_arduino_LED_ttl(fp_dict)

    # Update the dictionary with the new analysis data and set the flag
    fp_dict['fp_timing'].update({
        'dropped_frames_df': dropped_frames_df,
        'fp_frame_info': fp_time
    })
    fp_dict['fp_frame_analysis_run'] = True

    print(f"\n[{datetime.now():%H:%M:%S}] ({function_name}) FP frame analysis completed successfully for experiment {exp}.")
    
    return fp_dict


def preprocess_fp_data(df):
    """
    Preprocess the fp data by calculating frame intervals, 
    and adding frame time information.
    """
    df                               = df.copy()  # Make a copy to avoid modifying a view
    df['frame_interval_fp_time_sec'] = df['fp_time_sec'].diff()

    return df


def identify_dropped_FP_frames(df):
    """
    Identify dropped frames based on frame interval duration exceeding a threshold.
    """
    # Find dropped frames where the frame interval is too long or too short
    condition = (df['frame_interval_fp_time_sec'] > 1.1 * df['frame_interval_fp_time_sec'].median()) | \
                (df['frame_interval_fp_time_sec'] < 0.9 * df['frame_interval_fp_time_sec'].median())
    
    dropped_frames_indices = np.where(condition)[0]
    dropped_frames_count = np.round(df.loc[condition, 'frame_interval_fp_time_sec'] /
                                    df['frame_interval_fp_time_sec'].median(), 0) - 1

    return dropped_frames_indices, dropped_frames_count


def create_dropped_FP_frames_dataframe(df, dropped_frames_indices, dropped_frames_count):
    """
    Create a DataFrame containing information about dropped frames.
    """
    dropped_frames_df = df.iloc[dropped_frames_indices].copy()
    dropped_frames_df['dropped_frame_count'] = dropped_frames_count

    return dropped_frames_df
    

def plot_FP_frame_intervals(frame_df, dropped_frames_df):
    """
    Plot the interframe intervals and annotate dropped frames.
    This is used for analyzing FP frame timing.

    Args:
        frame_df (pd.DataFrame): DataFrame containing the frame timing data.
        dropped_frames_df (pd.DataFrame): DataFrame containing information about dropped frames.
    """
    plt.figure(figsize=(10, 3), constrained_layout=True)
    
    # Plotting the interframe intervals
    plt.plot(frame_df.index, frame_df['frame_interval_fp_time_sec'], 'k-', linewidth=0.5)
    plt.xlabel('FP Frame Number', fontsize=12)
    plt.ylabel('Interframe Interval [sec]', fontsize=12)
    plt.title('FP Interframe Interval Analysis', fontsize=13)


    # Calculate median for setting ylim
    median_interval = frame_df['frame_interval_fp_time_sec'].median()
    plt.ylim(0.99 * median_interval, 1.010 * median_interval)  # Set ylim based on median

    # Get the current ylim
    ymin, ymax = plt.ylim()

    # Draw and annotate the median line
    plt.axhline(y=median_interval, color='red', linestyle='--', linewidth=1)
    median_text = f'median: {median_interval:.4f}s\ncalculated fps: {1 / median_interval:.2f}'
    plt.gca().text(0.13, 0.95, median_text, transform=plt.gca().transAxes,
                   fontsize=8, verticalalignment='top', 
                   horizontalalignment='right', 
                   bbox=dict(boxstyle='round,pad=0.5', edgecolor='red', facecolor='white'))
    plt.annotate('', 
                 xy=(-4000, median_interval),  # Position on the median line (x, y) in data coordinates
                 xytext=(0.05, 0.84),          # Position of the textbox (x, y) in axes coordinates
                 textcoords='axes fraction',  # Textbox coordinates interpreted as axes fraction
                 arrowprops=dict(arrowstyle='->', color='red', lw=1))

    # Annotate dropped frames
    dropped_text = "\n".join([f"({int(index)}, {int(row['dropped_frame_count'])})" 
                               for index, row in dropped_frames_df.iterrows()])
    
    # Add the dropped frames text box in the lower right corner
    plt.gca().text(0.98, 0.05, dropped_text, transform=plt.gca().transAxes,
                   fontsize=8, verticalalignment='bottom', 
                   horizontalalignment='right', 
                   bbox=dict(boxstyle='round,pad=0.5', edgecolor='red', facecolor='white'))

    # Annotate dropped frames with red vertical lines
    for index, row in dropped_frames_df.iterrows():
        plt.axvline(x=int(index), color='red', linestyle='-', linewidth=2)

    # Show grid and plot
    plt.grid(True)
    plt.show()



#---------------------------------------------------------------------------------------------------------------------------------------------------



def calculate_LED_pulse_statistics(fp_dict):
    """
    Calculate statistics related to pulse width and interpulse width for Arduino TTL.
    This function assumes that the necessary data is nested in the `fp_dict` dictionary.
    """
    # Extract the necessary DataFrames and metadata from fp_dict
    arduino2fp_flips = fp_dict['fp_timing']['digital_IOs']['Input0']# DataFrame containing flip data
    fp_time_sec      = arduino2fp_flips['fp_time_sec']    # Time stamps for flips

    # Calculate pulse width (difference between consecutive flips with edge == 1)
    pulse_width = arduino2fp_flips.groupby(arduino2fp_flips['edge'].eq(1).cumsum())['fp_time_sec'].diff().dropna()
    avg_pulse_width = pulse_width.mean()
    sem_pulse_width = pulse_width.sem()

    # Identify long pulses using z-score (unusually long pulses)
    idx_long_pulses = pulse_width[(abs(zscore(pulse_width)) > 10)].index
    idx_long_pulses = list(idx_long_pulses - 1)

    # Calculate interpulse width (difference between consecutive flips with edge == 0)
    interpulse_width = arduino2fp_flips.groupby(arduino2fp_flips['edge'].eq(0).cumsum())['fp_time_sec'].diff().dropna()

    # Identify unusually long or short interpulses
    idx_long_interpulses = interpulse_width[(interpulse_width < 0.24) | (interpulse_width > 0.530)].index
    idx_long_interpulses = list(idx_long_interpulses - 1)

    # Return statistics and indices for long pulses and interpulses
    return {
        'avg_pulse_width': avg_pulse_width,
        'sem_pulse_width': sem_pulse_width,
        'idx_long_pulses': idx_long_pulses,
        'idx_long_interpulses': idx_long_interpulses,
    }


def print_LED_ttl_statistics(stats, fp_dict):
    """
    Print out TTL statistics such as average pulse width, unusually long pulses, and interpulses.
    """
    orange_bold = "\033[38;5;208m\033[1m"  # ANSI escape for bold orange
    reset_color = "\033[0m"  # ANSI reset color

    # Get the current function name using inspect
    function_name = inspect.currentframe().f_code.co_name

    print(f'\nArduino LED TTL summary:')
    print(f'    * Average pulse width +- s.e.m. [sec]: {round(stats["avg_pulse_width"], 6)} +- {round(stats["sem_pulse_width"], 6)}')

    arduino2fp_flips = fp_dict['fp_timing']['digital_IOs']['Input0']
    
    # Print details about long pulses
    if stats['idx_long_pulses']:
        print(f'    * {orange_bold}Unusually long pulse width (zscore >10, probably due to consecutive up and down edges missing)\n              found at fp_time_sec:{reset_color} {list(arduino2fp_flips.loc[stats["idx_long_pulses"], "fp_time_sec"])}')
    
    # Print details about long interpulses
    if stats['idx_long_interpulses']:
        print(f'    * {orange_bold}Unusually long interpulses (< 240ms, >530ms) found at fp_time_sec:{reset_color} {list(arduino2fp_flips.loc[stats["idx_long_interpulses"], "fp_time_sec"])}')

    # If neither long pulses nor interpulses exist, print a message
    if not stats['idx_long_pulses'] and not stats['idx_long_interpulses']:
        print(f'    * No unusually long pulses or interpulses detected!')


def analyze_arduino_LED_ttl(fp_dict):
    """
    Wrapper function that calculates and prints the TTL statistics for the experiment.
    """
    function_name = inspect.currentframe().f_code.co_name
    
    exp = fp_dict['expID']
    print(f"\n[{datetime.now():%H:%M:%S}] ({function_name}) Analyzing Arduino LED TTLs for experiment {exp}:")

    stats = calculate_LED_pulse_statistics(fp_dict)
    print_LED_ttl_statistics(stats, fp_dict)

    return None



#---------------------------------------------------------------------------------------------------------------------------------------------------

def extract_fluorescence_data(fp_dict, 
                              boxcar_kernel_len, 
                              normalization_method,
                              deinterleave_method='flags', 
                              ref_channel='LED415', interp_channel='LED470' 
                              ):
    """
    Extracts and deinterleaves fluorescence data from the DataFrame.
    It handles both old and new firmware versions automatically.
    """
    function_name = inspect.currentframe().f_code.co_name
    
    print(f"\n\n[{datetime.now():%H:%M:%S}] ({function_name}) Loading and extracting deinterleaved fluorescence data!")
    df = fp_dict['fp_fluorescence']['fp_interleaved_data'].copy()

    print(f"\n[{datetime.now():%H:%M:%S}] ({function_name}) Renaming fiber columns (fiber0_green, fiber1_green, fiber0_red,... etc.)")
    # Rename columns and detect firmware version
    df, firmware_version = rename_fiber_columns(df)
    print(f"[{datetime.now():%H:%M:%S}] ({function_name}) \033[1;38;5;214mFP3002 {firmware_version}\033[0m detected.")

    # Deinterleave the data based on flags or frame index
    DEinterleaved_fp_signals = deinterleave_fluorescence_data(df, deinterleave_method)

    print(f"[{datetime.now():%H:%M:%S}] ({function_name}) Interpolating \033[1;38;5;214m{interp_channel}\033[0m signal using \033[1;38;5;214m{ref_channel}\033[0m as reference.")
    # Interpolate signals to reference signal
    interpolated_fp_signals = interpolate_LED_signals(DEinterleaved_fp_signals, ref_channel=ref_channel, interp_channel=interp_channel)

    # Normalize the extracted signals
    norm_fp_signals = norm_FP_fluor_data(interpolated_fp_signals, boxcar_kernel_len, norm_method=normalization_method)

    # Update fp_dict with normalized data
    fp_dict['fp_fluorescence']['fp_DEinterleaved_data']                         = DEinterleaved_fp_signals
    fp_dict['fp_fluorescence']['fp_DEinterleaved_interpolated_data']            = interpolated_fp_signals
    fp_dict['fp_fluorescence']['fp_normalized_data']                            = norm_fp_signals
    fp_dict['fp_fluorescence']['fp_DEinterleaved_data']['normalization_method'] = normalization_method
    fp_dict['fp_fluorescence']['fp_DEinterleaved_data']['boxcar_kernel_length'] = boxcar_kernel_len

    return fp_dict


def rename_fiber_columns(df):
    """
    Renames the columns to a consistent naming scheme:
    - For old firmware: 'RegionG0' to 'RegionG7' become 'fiber0_green' to 'fiber7_green',
      and 'RegionR0' to 'RegionR7' become 'fiber0_red' to 'fiber7_red'.
    - For new firmware: 'G0' to 'G7' become 'fiber0_green' to 'fiber7_green',
      and 'R0' to 'R7' become 'fiber0_red' to 'fiber7_red'.

    Parameters:
    - df: DataFrame containing the fluorescence data (with 'Region' or 'G', 'R' columns).

    Returns:
    - df: DataFrame with columns renamed to the new consistent naming scheme.
    - firmware_version: A string indicating whether the firmware is 'old_firmware' or 'new_firmware'.
    """
    function_name = inspect.currentframe().f_code.co_name
    
    if any(col.startswith('Region') for col in df.columns):
        # Old firmware: Rename 'Region0G' to 'fiber0_green', 'Region1G' to 'fiber1_green', etc.
        firmware_version = 'firmware 0.5.6 or older.'
        df = df.rename(columns={col: f"fiber{col[6:-1]}_{'green' if col[-1] == 'G' else 'red'}"
                                for col in df.columns if col.startswith('Region')})
    else:
         # New firmware: Rename 'G0' to 'fiber0_green', 'G1' to 'fiber1_green', etc.
        firmware_version = 'firmware 0.6 or newer'
        df = df.rename(columns={col: f"fiber{int(col[1])}_green" for col in df.columns if col.startswith('G')})
        df = df.rename(columns={col: f"fiber{int(col[1])}_red" for col in df.columns if col.startswith('R')})

    return df, firmware_version


def get_num_fibers(df):
    """
    Extracts the highest fiber index from the column names and returns the total number of fibers.
    
    Parameters:
    - df: The dataframe containing fiber data.
    
    Returns:
    - num_fibers: The total number of fibers.
    """
    # Regular expression to match fiberX_green or fiberX_red columns
    fiber_columns = [col for col in df.columns if re.match(r'fiber(\d+)_green|fiber(\d+)_red', col)]
    
    # Extract the indices from the column names and get the highest index
    fiber_indices = [int(re.search(r'\d+', col).group()) for col in fiber_columns]
    
    # The number of fibers is the highest index + 1 (since indexing starts at 0)
    num_fibers = max(fiber_indices) + 1 if fiber_indices else 0
    
    return num_fibers


def deinterleave_fluorescence_data(dx, deinterleave_method='flags'):
    """
    Deinterleaves the data based on flags or frame index. If flags are unreliable, 
    it will split the data every second or third frame.
    
    Returns:
        fp_signals (dict): A dictionary containing deinterleaved dataframes for each wavelength.
    """
    
    function_name = inspect.currentframe().f_code.co_name
    
    df = dx.copy()
    
    # Get unique flags from the 'Flags' column
    unique_flags = df['Flags'].unique()
    
    # Initialize an empty dictionary to store the deinterleaved signals
    fp_signals = {}

    # Helper function to rename columns based on wavelength
    def rename_columns(fp, wavelength):
        renamed_columns = {}
        for col in fp.columns:
            if 'green' in col:
                # Replace 'green' with the appropriate wavelength (e.g., '415nm', '470nm', etc.)
                new_col = col.replace('green', f'{wavelength}')
                renamed_columns[col] = new_col
        return fp.rename(columns=renamed_columns)

    # Determine the deinterleave method based on flags
    if deinterleave_method == 'flags':        
        # Deinterleave by applying the is_kth_bit_set to filter based on whether the 0th, 1st, or 2nd bit is set (-> 415nm, 470nm, 560nm)
        print(f"[{datetime.now():%H:%M:%S}] ({function_name}) \033[1;38;5;214m'FLAGS'\033[0m used for deinterleaving multiplexed fluorescence signals.")
        fp_signals['LED415'] = rename_columns(df[df['Flags'].apply(lambda x: is_kth_bit_set(x, 0))], '415nm').reset_index(drop=True)
        fp_signals['LED470'] = rename_columns(df[df['Flags'].apply(lambda x: is_kth_bit_set(x, 1))], '470nm').reset_index(drop=True)
        fp_signals['LED560'] = rename_columns(df[df['Flags'].apply(lambda x: is_kth_bit_set(x, 2))], '560nm').reset_index(drop=True)
        
    elif deinterleave_method == '2nd_415':
        # If using LED415 and flags are unreliable, extract every 2nd frame        
        print(f"[{datetime.now():%H:%M:%S}] ({function_name}) \033[1;38;5;214mEVERY 2nd frame\033[0m used for deinterleaving multiplexed fluorescence signals.")
        frame_skip = 2
        fp_signals['LED415'] = rename_columns(df[df.index % frame_skip == 0], '415nm').reset_index(drop=True)
        fp_signals['LED470'] = rename_columns(df[df.index % frame_skip == 1], '470nm').reset_index(drop=True)
        fp_signals['LED560'] = pd.DataFrame()
        
    elif deinterleave_method == '2nd_560':
        # If using red LED and flags are unreliable, extract every 2nd frame  
        print(f"[{datetime.now():%H:%M:%S}] ({function_name}) \033[1;38;5;214mEVERY 2nd frame and red LED\033[0m used for deinterleaving multiplexed fluorescence signals.")   
        frame_skip = 2
        fp_signals['LED415'] = pd.DataFrame()
        fp_signals['LED470'] = rename_columns(df[df.index % frame_skip == 1], '470nm').reset_index(drop=True)
        fp_signals['LED560'] = rename_columns(df[df.index % frame_skip == 2], '560nm').reset_index(drop=True)
   
    else:
        print(f"[{datetime.now():%H:%M:%S}] ({function_name}) \033[1;38;5;214mNo data extracted!\033[0m")   
        fp_signals['LED415'] = pd.DataFrame()  # Empty dataframe if there are no L415 frames
        fp_signals['LED470'] = pd.DataFrame()  # Empty dataframe if there are no L470 frames
        fp_signals['LED560'] = pd.DataFrame()  # Empty dataframe if there are no L560 frames

    return fp_signals


def is_kth_bit_set(n, k): 
    '''
    Checks if the kth bit of an integer n is set to 1 (True) or 0 (False).
    
    Parameters:
    - n: integer, representing the value to check
    - k: integer, the bit position to check (0-indexed from the right)
    
    Returns:
    - True if the kth bit is set to 1, False otherwise.
    '''
    return (n & (1 << k)) != 0

    
def interpolate_LED_signals(fp_signals, ref_channel, interp_channel):
    """
    Interpolates a given signal to match the time axis of another signal.
    Merges the reference channel and interpolated channel into one DataFrame containing the time of the reference
    and 'fiber' columns from both channels.

    Parameters:
    - fp_signals: Dictionary containing DataFrames for 'LED415', 'LED470', and 'LED560'.
    - ref_channel: The reference channel to interpolate to (either 'LED415' or 'LED560').
    - interp_channel: The channel to interpolate (either 'LED470' or 'LED560').

    Returns:
    - merged_signals: A DataFrame with time from the reference channel and 'fiber' columns from both channels.
    """
    
    # Extract the input DataFrames from the dictionary directly
    ref_fp                = fp_signals[ref_channel]
    signal_to_interpolate = fp_signals[interp_channel]
    
    # Initialize the merged DataFrame with the time column from the reference channel
    merged_signals = ref_fp[['fp_time_sec']].copy()
    
    # Get all columns containing 'fiber' in their name for both channels
    ref_fiber_columns    = [col for col in ref_fp.columns if 'fiber' in col]
    interp_fiber_columns = [col for col in signal_to_interpolate.columns if 'fiber' in col]

    # Add the fiber columns from the reference channel
    for col in ref_fiber_columns:
        merged_signals[col] = ref_fp[col].copy()

    # Interpolate and add fiber columns from the interpolated channel
    for col in interp_fiber_columns:
        # Perform the interpolation
        tmp = np.interp(ref_fp['fp_time_sec'].to_numpy(), 
                        signal_to_interpolate['fp_time_sec'].to_numpy(), 
                        signal_to_interpolate[col].to_numpy())
        
        # Add the interpolated values to the merged DataFrame
        merged_signals[col] = tmp

    # Optionally drop columns that are not needed (e.g., 'fp_frame' or 'Flags')
    merged_signals = merged_signals.drop(columns=[col for col in merged_signals.columns if col in ['ComputerTimestamp', 'Flags']], errors='ignore')
    
    return merged_signals


def norm_FP_fluor_data(dx, boxcar_kernel_len, norm_method):
    '''
    Normalize FP fluorescence signals for each fiber in the dataset using one of the specified normalization methods.
    
    Parameters:
    - df: pandas DataFrame containing the fluorescence data. The DataFrame should have columns for the fiber signals (e.g., 'fiber0_415nm', 'fiber0_470nm', etc.), as well as a time column ('fp_time_sec').
    - boxcar_kernel_len: Length of the boxcar kernel for smoothing the fiber signals. If set to 0, no smoothing is applied.
    - norm_method: The method used for normalization. Options are:
        - 'biexp': Apply bi-exponential fitting and z-score normalization.
        - 'airPLS': Apply adaptive iteratively reweighted Penalized Least Squares (airPLS) for baseline correction and z-score normalization.

    Returns:
    - df: The DataFrame with updated normalized columns for each fiber, including baseline fits and zDF/F values.
    
    Notes:
    - The function applies the specified normalization method to all fiber columns (those containing 'fiber' in the column name).
    - If `boxcar_kernel_len` is greater than 0, it will smooth the fiber signal using a boxcar filter before applying the normalization method.
    - For 'biexp', a bi-exponential function is fitted to the 415nm LED signal, and this fit is used to baseline correct the 470nm LED signal.
    - For 'airPLS', adaptive iteratively reweighted Penalized Least Squares (airPLS) is used for baseline correction on both the 415nm and 470nm LED signals, followed by z-score normalization.
    '''

    function_name = inspect.currentframe().f_code.co_name
    
    df = dx.copy()

    # Smoothen fiber_signals with boxcar low pass filter
    if boxcar_kernel_len > 0:
        print(f"[{datetime.now():%H:%M:%S}] ({function_name}) \033[1;38;5;214mSignal filtered\033[0m with boxcar kernel length {boxcar_kernel_len}.")
        kernel = np.ones(boxcar_kernel_len) / boxcar_kernel_len
        fiber_cols = {col.split('_')[0] for col in df.columns if 'fiber' in col}  # Get unique fiber identifiers (e.g., 'fiber0', 'fiber1')

        for fiber in fiber_cols:
            # Process each fiber's 415nm and 470nm columns
            for wavelength in ['415nm', '470nm']:  # Adjust for additional wavelengths if needed
                col_name = f'{fiber}_{wavelength}'
                if col_name in df.columns:
                    df.loc[:, col_name] = filtfilt(kernel, 1, df.loc[:, col_name])
    else:
        print(f"[{datetime.now():%H:%M:%S}] ({function_name}) \033[1;38;5;214mSignals NOT filtered\033[0m (boxcar kernel length is 0).")

    
    # Iterate over all unique fiber identifiers and sort them numerically
    fiber_cols = sorted({col.split('_')[0] for col in df.columns if 'fiber' in col}, 
                        key=lambda x: int(x.split('fiber')[1]))  # Sort based on the numerical part

    
    for fiber in fiber_cols:
        # Apply normalization based on the selected method
         
        if norm_method == 'biexp':
            df = apply_biexp_normalization(df, fiber)
        
        if norm_method == 'airPLS':
            df = apply_airPLS_normalization(df, fiber)

        if norm_method == 'Luescher':
            df = apply_peak_thresholding_normalization(df, fiber, threshold_percentile=95, baseline_duration_sec=300)

    if norm_method == 'Luescher':
        print(f"[{datetime.now():%H:%M:%S}] ({function_name}) Deinterleaved FP fluorescence data normalized using the\033[1;38;5;214m {norm_method}\033[0m method (UNTESTED!).")

    else:
        print(f"[{datetime.now():%H:%M:%S}] ({function_name}) Deinterleaved FP fluorescence data normalized using the\033[1;38;5;214m {norm_method}\033[0m method.")
    
    return df


def apply_biexp_normalization(df, fiber):
    """
    Apply bi-exponential fitting for baseline correction and zscore normalization.
    
    Parameters:
    - df: The DataFrame containing the fiber data.
    - fiber: The base name of the fiber (e.g., 'fiber0').

    Returns:
    - df: The DataFrame with the zDF/F normalized values.
    
    Notes:
    - This function fits a bi-exponential function to the 415nm signal of the selected fiber.
    - The fitted 415nm signal is then used to baseline correct the 470nm signal.
    - The baseline-corrected signal is z-scored to compute the normalized dF/F (zDF/F).
    """
    # Fit bi-exponential to LED415 signals for each fiber
    time_array    = df['fp_time_sec'].to_numpy()
    y_array_biexp = df[fiber + '_415nm'].to_numpy()

    # Fit the bi-exponential model
    popt_biexp, _ = optimize.curve_fit(fit_biexp, time_array, y_array_biexp, 
                                       p0=[time_array.min(), 0, 0, 0, 0], maxfev=50000)

    # Fit bi-exponential LED415fit to LED415-interpolated 470nm signal
    x     = fit_biexp(time_array, *popt_biexp).reshape((-1, 1))
    y     = df[fiber + '_470nm'].to_numpy()
    model = LinearRegression()
    model.fit(x, y)
    df[fiber + '_baseline_fit'] = model.coef_ * fit_biexp(time_array, *popt_biexp) + model.intercept_

    # Calculate zdF/F
    df[fiber + '_zDF/F'] = zscore(df[fiber + '_470nm'] - df[fiber + '_baseline_fit'])
    
    return df


def apply_airPLS_normalization(df, fiber):
    """
    Apply adaptive iteratively reweighted Penalized Least Squares (airPLS) for baseline correction and zscore normalization.
    
    Parameters:
    - df: The DataFrame containing the fiber data.
    - fiber: The base name of the fiber (e.g., 'fiber0').

    Returns:
    - df: The DataFrame with the zDF/F normalized values.
    
    Notes:
    - This function applies airPLS baseline correction to both the 415nm and 470nm signals for the selected fiber.
    - The baseline-corrected signals are z-scored, and the baseline is further corrected using a linear regression fit between the 415nm and 470nm signals.
    - The normalized dF/F (zDF/F) is computed as the difference between the z-scored 470nm signal and the baseline fit.
    """
    # Baseline correction of each signal using adaptive iteratively reweighted Penalized Least Squares (airPLS)
    # then zscore the difference
    df[fiber + '_415nm_corr'] = zscore(df[fiber + '_415nm'].to_numpy() - airPLS(df[fiber + '_415nm'].to_numpy()))
    df[fiber + '_470nm_corr'] = zscore(df[fiber + '_470nm'].to_numpy() - airPLS(df[fiber + '_470nm'].to_numpy()))

    # Least square fit of fitted and zscored LED415 to LED415-interpolated 470nm signal
    x     = df[fiber + '_415nm_corr'].to_numpy().reshape((-1, 1))
    y     = df[fiber + '_470nm_corr'].to_numpy()
    model = LinearRegression(positive=True)
    model.fit(x, y)
    df[fiber + '_baseline_fit'] = model.coef_ * df[fiber + '_415nm_corr'].to_numpy() + model.intercept_

    # Calculate the normalized dF/F (z dF/F)
    df[fiber + '_zDF/F'] = df[fiber + '_470nm_corr'] - df[fiber + '_baseline_fit']

    return df


def apply_peak_thresholding_normalization(df, fiber, threshold_percentile=95, baseline_duration_sec=300):
    """
    Normalize fluorescence signals using peak extraction and scaling based on the pre-behavior baseline.
    
    Parameters:
    - df: pandas DataFrame containing the fluorescence data with columns like 'fiber0_415nm', 'fiber0_470nm', etc.
    - fiber: The fiber identifier (e.g., 'fiber0').
    - threshold_percentile: The percentile of the peak amplitudes to consider as the top 5% (default is 95).
    - baseline_duration_sec: Duration in seconds for the baseline period (default is 300 seconds = 5 minutes).
    
    Returns:
    - df: The DataFrame with the normalized signals using the calculated scaling factor.
    
    Notes:
    - This method assumes that the raw 415nm signal is used as the baseline signal (F0) and the 470nm signal is the fluorescence signal (F).
    - The function computes delta F/F0, extracts peaks from the pre-behavior baseline, and calculates the scaling factor based on the top 5% of those peaks.
    - The scaling factor is used to normalize the entire trace.
    """
    
    # Extract the raw 415nm and 470nm signals
    time_array   = df['fp_time_sec'].to_numpy()
    signal_415nm = df[fiber + '_415nm'].to_numpy()
    signal_470nm = df[fiber + '_470nm'].to_numpy()
    
    # Find the start of the baseline period (first 5 minutes from the start of the recording)
    baseline_start_time = time_array[0]  # The first time point in the signal
    baseline_end_time   = baseline_start_time + baseline_duration_sec  # 5 minutes later
    
    # Get the indices that correspond to this time period
    baseline_start_idx = np.searchsorted(time_array, baseline_start_time)
    baseline_end_idx   = np.searchsorted(time_array, baseline_end_time)
    
    # Step 1: Baseline correction using regression (simple linear regression or similar)
    # Assuming simple linear regression for this case:
    model        = LinearRegression()
    model.fit(signal_415nm[baseline_start_idx:baseline_end_idx].reshape(-1, 1), signal_470nm[baseline_start_idx:baseline_end_idx])
    baseline_fit = model.coef_ * signal_415nm + model.intercept_
    
    # Step 2: Calculate delta F/F0 (change relative to baseline)
    delta_F                  = signal_470nm - baseline_fit
    F0                       = baseline_fit
    df[fiber + '_deltaF_F0'] = delta_F / F0  # This will be your ΔF/F0 trace
    
    # Step 3: Peak extraction within the baseline period
    baseline_signal = df[fiber + '_deltaF_F0'][baseline_start_idx:baseline_end_idx]
    
    # Extract peaks from the baseline signal (assuming local maxima)
    peaks, _        = find_peaks(baseline_signal)
    peak_amplitudes = baseline_signal[peaks]
    
    # Step 4: Threshold the peak amplitudes to get the top 5% of them
    threshold_value = np.percentile(peak_amplitudes, threshold_percentile)
    high_peaks      = peak_amplitudes[peak_amplitudes >= threshold_value]
    
    # Step 5: Calculate scaling factor (average of the top 5% peak amplitudes)
    scaling_factor = np.mean(high_peaks)
    
    # Step 6: Normalize the entire trace by the scaling factor
    df[fiber + '_normalized'] = df[fiber + '_deltaF_F0'] / scaling_factor
    
    return df


def fit_biexp(x, a, k1, b, k2, c):
    '''
    bi-exponential fit function   
    '''
    
    return a*np.exp(x*k1) + b*np.exp(x*k2) + c


def whittaker_smooth(x, w, lambda_, differences=1):
    '''
    Penalized least squares algorithm for background fitting
    
    input
        x:           input data (i.e. chromatogram of spectrum)
        w:           binary masks (value of the mask is zero if a point belongs to peaks and one otherwise)
        lambda_:     parameter that can be adjusted by user. The larger lambda is,  
                     the smoother the resulting background
        differences: integer indicating the order of the difference of penalties
    
    output
        the fitted background vector
    '''
    
    X          = np.matrix(x)
    m          = X.size
    i          = np.arange(0, m)
    E          = eye(m, format='csc')
    D          = E[1:]-E[:-1] # numpy.diff() does not work with sparse matrix. This is a workaround.
    W          = diags(w, 0, shape=(m,m) )
    A          = csc_matrix(W+(lambda_*D.T*D))
    B          = csc_matrix(W*X.T)
    background = spsolve(A, B)
    
    return np.array(background)


def airPLS(x, lambda_= 5e9, porder = 2, itermax = 50):
    '''
    Adaptive iteratively reweighted penalized least squares for baseline fitting
    
    input
        x: input data (i.e. chromatogram of spectrum)
        lambda_: parameter that can be adjusted by user. The larger lambda is,  
        the smoother the resulting background, z
        porder: adaptive iteratively reweighted penalized least squares for baseline fitting
    
    output
        the fitted background vector
    '''
    m = x.shape[0]
    w = np.ones(m)
    
    for ii in range(1, itermax+1):
        z    = whittaker_smooth(x, w, lambda_, porder)
        d    = x-z
        dssn = np.abs(d[d<0].sum())
        
        if(dssn < 0.001*(abs(x)).sum() or ii==itermax):
            if(ii==itermax): print('WARNING max iteration reached!')
            break
    
        w[d>=0] = 0 # d>0 means that this point is part of a peak, so its weight is set to 0 in order to ignore it
        w[d<0]  = np.exp(ii*np.abs(d[d<0])/dssn)
        w[0]    = np.exp(ii*(d[d<0]).max()/dssn) 
        w[-1]   = w[0]
        
    return z
