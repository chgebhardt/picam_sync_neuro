# Standard Library Imports
from datetime import datetime
import inspect
import os
import re
from pathlib import Path
import pickle

# Third-Party Libraries
import numpy as np
import pandas as pd
import h5py
from scipy.stats import zscore
from scipy.signal import find_peaks
import glob


def load_picam_data(homedir, expID, verbose=True):
    """
    Detects how many picams there are and creates a nested dictionary for each camera.
    Optionally saves the dictionary to a pickle file if `save=True`.
    """
    function_name = inspect.currentframe().f_code.co_name
    print(f'[{datetime.now():%H:%M:%S}] ({function_name}) Loading picamera data for experiment {expID}')

    # Attempt to load an existing pickle file
    picam_dict = load_picam_pickle_file(homedir, expID)
    if not picam_dict:
        
        # Initialize data structure
        picam_list = find_picams(homedir, expID)
        picam_dict = initialize_picam_dict(homedir, expID, picam_list)

    else:
        print(f"\n[{datetime.now():%H:%M:%S}] ({function_name}) Found and loaded existing picam data previously saved on {picam_dict['picam_data_save_datetime']}!")
        
    # Print a summary of the loaded or newly created picam data
    print(f"\n[{datetime.now():%H:%M:%S}] ({function_name}) Experiment Type / Behavior paradigm: \033[38;5;208m\033[1m{picam_dict.get('experiment_type', 'Unknown')}\033[0m")
    
    print(f'\n[{datetime.now():%H:%M:%S}] ({function_name}) PICAM Acquisition SUMMARY:')
    
    for picam_id in picam_dict['picam_list']:
        print_metadata_frames_summary(
            picam_id,
            picam_dict[picam_id]['picam_metadata'],
            picam_dict[picam_id]['picam_timing']['picam_frame_info']
        )

    return picam_dict


def initialize_picam_dict(homedir, expID, picam_list):
    """
    Initializes the picam dictionary from scratch if no pickle file exists.
    """
    function_name = inspect.currentframe().f_code.co_name
    
    picam_dict = {
        'expID': expID,
        'picam_data_save_datetime': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        'picam_list': picam_list,
        'experiment_type': [],
        'picam_frame_analysis_run': False # set the 'picam frame analysis run' flag
    }

    for picam_id in picam_list:

        # Load metadata
        picam_metadata = load_picam_metadata(homedir, expID, picam_id)
        if not picam_metadata:
            print(f'[{datetime.now():%H:%M:%S}] ({function_name}) No metadata found for picam ID: {picam_id}. Skipping.')
            continue

        # Append experiment type if available
        if 'behavior_paradigm' in picam_metadata:
            picam_dict['experiment_type'].append(picam_metadata['behavior_paradigm'])

        # Load and process frame time data
        frame_df = load_picamera_clock_data(homedir, expID, picam_id)
        if frame_df is None:
            print(f'[{datetime.now():%H:%M:%S}] ({function_name}) No frame timing data found for picam ID: {picam_id}. Skipping.')
            continue

        # Load ethogram and tracking data
        ethogram_range, behavior_trials  = load_ethogram(homedir, expID, picam_id)
        pup_location, pup_nodes_dict     = load_SLEAP_tracking_data(homedir, expID, picam_id, 'pup')
        adult_location, adult_nodes_dict = load_SLEAP_tracking_data(homedir, expID, picam_id, 'adult')

        # Load LED blink data
        picam_LEDsignal, picam_LED_blinks = load_picam_LED_data(homedir, expID, picam_id, frame_df['GPU_time_sec'].values)

        # Store tracking data
        animal_tracking = {
            'pup': {
                'location': pup_location,
                'node_names': pup_nodes_dict
            },
            'adult': {
                'location': adult_location,
                'node_names': adult_nodes_dict
            }
        }

        # Store timing data
        picam_timing = {
            'picam_frame_info': frame_df,
            'picam_LEDsignal':  picam_LEDsignal,
            'picam_LED_blinks': picam_LED_blinks
        }

        # Populate picam_dict
        picam_dict[picam_id] = {
            'picam_metadata':  picam_metadata,
            'ethogram_range':  ethogram_range,
            'behavior_trials': behavior_trials,
            'animal_tracking': animal_tracking,
            'picam_timing':    picam_timing
        }

    # Deduplicate and validate experiment types
    unique_experiment_types = list(set(picam_dict['experiment_type']))
    if len(unique_experiment_types) > 1:
        print(f'[{datetime.now():%H:%M:%S}] ({function_name}) ERROR: Mismatch in behavior_paradigm values: {unique_experiment_types}')
        raise ValueError(f"Mismatch in behavior_paradigm values between the picams: {unique_experiment_types}")
    picam_dict['experiment_type'] = unique_experiment_types[0] if unique_experiment_types else None

    return picam_dict


def find_picams(homedir, expID):
    '''
    Finds unique picam modifiers (pic1, pic2, ...) in the working folder.
    Only processes .txt files.
    '''
    
    folder = os.path.join(homedir, expID, '01_picams', '01_raw')

    # Get unique picam identifiers from .txt files containing 'pic'
    picam_identifiers = {re.split('[_.]', f)[2] for f in os.listdir(folder) 
                         if f.endswith('.txt') and 'pic' in f and len(re.split('[_.]', f)) > 2}

    picam_list = sorted(picam_identifiers)  # Sort the unique identifiers

    function_name = inspect.currentframe().f_code.co_name    
    print(f'\n[{datetime.now():%H:%M:%S}] ({function_name}) {len(picam_list)} picamera(s) found: {picam_list}')
    
    if not picam_list:
        print("No picamera found!")
        return []
    
    return picam_list
    

def load_picam_metadata(homedir, expID, picam_id):
    '''
    Extracts the metadata of a picamera.
    '''
    
    folder = f"{homedir}{expID}/01_picams/01_raw/"
    file_path = f"{folder}{expID}_{picam_id}.txt"
    
    # Load metadata from CSV
    picam_metadata = pd.read_csv(file_path, header=0, index_col=0, delimiter=':').to_dict()[f"{expID}_{picam_id}"]

    # Convert specific keys to the correct data types
    for key in ['animalID', 'bitrate']:
        if pd.notna(picam_metadata.get(key)):  # Check for NaN
            picam_metadata[key] = int(picam_metadata[key])
        # Else leave it as NaN (default behavior)

    for key in ['video_duration_mins', 'pup_age_days', 'fps', 'shutterspeed_us']:
        if pd.notna(picam_metadata.get(key)):  # Check for NaN
            picam_metadata[key] = float(picam_metadata[key])
        # Else leave it as NaN (default behavior)

    function_name = inspect.currentframe().f_code.co_name     
    print(f'\n[{datetime.now():%H:%M:%S}] ({function_name}) {picam_id} metadata loaded!')
    
    return picam_metadata


def print_metadata_frames_summary(picam_id, picam_metadata, frame_df):
    """
    Print summary of the metadata.
    """
    total_frames  = len(frame_df.index)
    
    print(f"\n   Metadata ({picam_id}):")
    print(f"   Framerate [fps]: {picam_metadata['fps']}")
    print(f"   Video duration [min]: {picam_metadata['video_duration_mins']}")
    print(f"   Resolution [px]: {picam_metadata['resolution_px']}")
    print(f"   Shutter speed [us]: {picam_metadata['shutterspeed_us']}")
    print(f"   Bitrate [bit/sec]: {picam_metadata['bitrate']}")

    
def load_picamera_clock_data(homedir, expID, picam_id):
    """
    Load picamera clock data from the specified CSV file and preprocess it.
   
    - loads csv files from working dir:
        # csv file key
        # columns: frame_index, frame_type, GPU_time_us, time.time()
        #
        # frame_types: 
        # normal frame = 0
        # key_frame    = 1
        # sps_header   = 2
        # motion_data  = 3
    """
    
    folder = os.path.join(homedir, expID, '01_picams', '01_raw')
    fname = f"{expID}_{picam_id}_clock.csv"
    picam_raw = np.genfromtxt(os.path.join(folder, fname), delimiter=',', skip_header=1)
    
    # Fix first keyframe timestamp and remove invalid entries
    picam_raw[1, 2] = 0
    valid_frame_data = picam_raw[picam_raw[:, 2] != -1000]

    # Preprocess the valid data to create frame_df
    frame_df = preprocess_frame_data(valid_frame_data)

    # Log the loading status with function name and timestamp
    function_name = inspect.currentframe().f_code.co_name     
    print(f'[{datetime.now():%H:%M:%S}] ({function_name}) {picam_id} frame time data loaded!')

    return frame_df


def preprocess_frame_data(picam_raw):
    """
    Pre-Process the raw frame data into a DataFrame with timestamps and intervals.
    """
    frame_df = pd.DataFrame(picam_raw, columns=['frame_index', 'frame_type', 'GPU_time_us', 'time.time_sec'])
    frame_df['GPU_time_sec'] = frame_df['GPU_time_us'] / 1_000_000
    frame_df['frame_interval_GPU_time_sec'] = frame_df['GPU_time_sec'].diff()
   
    return frame_df


def load_ethogram(homedir, expID, picam_id):
    """
    Main function to load, preprocess, and validate the ethogram data.
    """
    function_name = inspect.currentframe().f_code.co_name
    
    # Load data
    ethogram_range, behavior_trials = load_ethogram_data(homedir, expID, picam_id)
    
    # Check if ethogram data was successfully loaded
    if ethogram_range.empty:
        return ethogram_range, behavior_trials  # Return empty DataFrames if no data was loaded
    
    # Define the expected behavior categories based on the ethogram type
    behavior_categories_1 = ['attack', 'close2pup', 'licking','pup_added']
    behavior_categories_2 = ['close2ensure', 'ensure_added', 'licking_bout']
    behavior_categories_3 = ['approach', 'attend', 'background', 'exploration', 'facial_investigation', 
                             'licking_huddling', 'pick_up', 'pup_added', 'transport', 'transport_homebase']
    
    
    # Check which behavior categories are in the data and validate accordingly
    if 'attacked' in ethogram_range.index:
        if not check_behavior_categories(ethogram_range, behavior_categories_1, picam_id):
            return pd.DataFrame()  # Return empty if validation fails
    elif 'ensure_added' in ethogram_range.index:
        if not check_behavior_categories(ethogram_range, behavior_categories_2, picam_id):
            return pd.DataFrame()  # Return empty if validation fails
    elif 'retrieved' in ethogram_range.index:
        if not check_behavior_categories(ethogram_range, behavior_categories_3, picam_id):
            return pd.DataFrame()  # Return empty if validation fails
    
    # Preprocess data to adjust for 1-based indexing and remove dummy rows
    ethogram_range, behavior_trials = preprocess_ethogram_data(ethogram_range)
    
    # Validate frame consistency
    validate_frame_consistency(ethogram_range, picam_id)

    return ethogram_range, behavior_trials

def load_ethogram_data(homedir, expID, picam_id):
    """
    Loads the ethogram CSV file and performs initial checks.
    """
    function_name = inspect.currentframe().f_code.co_name
    folder        = os.path.join(homedir, expID, '01_picams', '04_ethograms')
    filepath      = os.path.join(folder, f"{expID}_{picam_id}_manual_ethogram.csv")
    
    if os.path.isfile(filepath):
        ethogram_range = pd.read_csv(filepath, header=0, index_col=0, delimiter=';')
        print(f"[{datetime.now():%H:%M:%S}] ({function_name}) {picam_id}: Manually determined ethogram found and loaded!")
        return ethogram_range, pd.DataFrame(columns=['start_frame', 'end_frame']).set_index(pd.Index([])).rename_axis('category')

    else:
        print(f"[{datetime.now():%H:%M:%S}] ({function_name}) {picam_id}: \033[38;5;208m\033[1mNo manually determined ethogram found!!!\033[0m")
        return pd.DataFrame(columns=['start_frame', 'end_frame']).set_index(pd.Index([])).rename_axis('category'), pd.DataFrame(columns=['start_frame', 'end_frame']).set_index(pd.Index([])).rename_axis('category')

def check_behavior_categories(ethogram_range, behavior_categories, picam_id):
    """
    Checks if the expected behavior categories are present exactly, without any missing or extra categories.
    """
    function_name = inspect.currentframe().f_code.co_name
    
    # Get the unique behavior categories from the ethogram data
    unique_categories = set(ethogram_range.index.unique())  # Use set for comparison
    
    # Check if the unique categories match exactly with the expected categories
    if unique_categories != set(behavior_categories):
        missing_categories = set(behavior_categories) - unique_categories
        extra_categories = unique_categories - set(behavior_categories)

        # Print missing and extra categories
        if missing_categories:
            print(f"[{datetime.now():%H:%M:%S}] ({function_name}) {picam_id}: \033[38;5;208m\033[1mMissing behavior categories: {', '.join(missing_categories)}. Loading aborted.\033[0m")
        
        if extra_categories:
            print(f"[{datetime.now():%H:%M:%S}] ({function_name}) {picam_id}: \033[38;5;208m\033[1mUnexpected behavior categories found: {', '.join(extra_categories)}. Loading aborted.\033[0m")
        
        return False
    
    return True

def preprocess_ethogram_data(ethogram_range):
    """
    Preprocesses the ethogram data by correcting for 1-based indexing and removing NaNs.
    Identifies specific rows based on index and separates them into a new dataframe.
    """
    function_name = inspect.currentframe().f_code.co_name

    # Adjust for 1-based to 0-based indexing
    ethogram_range[['start_frame', 'end_frame']] -= 1

    # Drop rows with NaNs in 'start_frame' or 'end_frame'
    ethogram_range.dropna(subset=['start_frame', 'end_frame'], inplace=True)

    # Define potential index values to check in order to generate trials dataframe
    target_indices = ['pup_added', 'ensure_added']
    trials         = None
    # Check if any of the conditions are met and handle the row extraction
    for index in target_indices:
        if index in ethogram_range.index:
            trials         = ethogram_range.loc[ethogram_range.index == index]
            ethogram_range = ethogram_range[ethogram_range.index != index]
            break  # Exit once a match is found

    # Define potential column names to check in order to generate trials dataframe
    column_checks  = ['attacked', 'retrieved']
    # Check for behavior column
    for column in column_checks:
        if column in ethogram_range.columns:
            # Same logic for 'pup_added' or 'ensure_added' cases
            if trials is None:
                trials         = ethogram_range.loc[ethogram_range.index == 'pup_added']
                ethogram_range = ethogram_range[ethogram_range.index != 'pup_added']

    # Clean the trials and ethogram_range dataframes
    if trials is not None:
        trials = trials.dropna(axis=1).astype(int)
    
    #ethogram_range = ethogram_range.dropna(axis=1).astype(int)

    return ethogram_range, trials



def check_frame_order(df, start_col='start_frame', end_col='end_frame'):
    """
    Checks that each end_frame is greater than or equal to the start_frame.
    Returns invalid rows if any are found.
    """
    invalid_frame_order = df[df[end_col] < df[start_col]]
    return invalid_frame_order

def check_overlapping_intervals(df, start_col='start_frame', end_col='end_frame'):
    """
    Checks for overlapping intervals where the end_frame of a row is greater than the start_frame of the next row.
    Returns overlapping intervals if any are found.
    """
    overlapping_intervals = df[df[end_col] >= df[start_col].shift(-1)]
    return overlapping_intervals


def check_category_within_category(df, outer_category, inner_category, start_col, end_col):
    """
    Checks if rows of the `inner_category` are fully contained within rows of the `outer_category`.
    Returns invalid rows if any are found.
    """
    outer_rows = df[df.index == outer_category]
    inner_rows = df[df.index == inner_category]

    invalid_ranges = []
    for inner_idx, inner_row in inner_rows.iterrows():
        # Find the closest preceding outer row
        preceding_outer = outer_rows[
            outer_rows[start_col] <= inner_row[start_col]
        ].iloc[-1:]  # Take the last row only (closest preceding)

        if not preceding_outer.empty:
            outer_row = preceding_outer.iloc[0]
            if not (
                inner_row[start_col] >= outer_row[start_col]
                and inner_row[end_col] <= outer_row[end_col]
            ):
                invalid_ranges.append(inner_row)

    return pd.DataFrame(invalid_ranges)



def validate_frame_consistency(ethogram_range, picam_id):
    """
    Validates start and end frame consistency for ethogram data based on the input configuration.
    
    Automatically determines the outer and inner categories (e.g., 'close2pup'/'attack', 
    'close2ensure'/'licking_bout') based on the input DataFrame structure.
    
    Parameters:
        ethogram_range (pd.DataFrame): Input DataFrame.
        picam_id (str): Identifier for the dataset.
    """

    function_name = inspect.currentframe().f_code.co_name

    # Determine configuration based on DataFrame structure
    if 'attacked' in ethogram_range.columns:
        outer_category = 'close2pup'
        inner_category = 'attack'
    elif 'close2ensure' in ethogram_range.index:
        outer_category = 'close2ensure'
        inner_category = 'licking_bout'
    else:
        outer_category = None
        inner_category = None

    if outer_category and inner_category:
        # Validate `outer_category` rows
        outer_rows = ethogram_range[ethogram_range.index == outer_category]
        invalid_outer_order = check_frame_order(outer_rows)
        if not invalid_outer_order.empty:
            print(f"[{datetime.now():%H:%M:%S}] ({function_name}) {picam_id}: Invalid frame order in '{outer_category}':\n{invalid_outer_order}\n")

        overlapping_outer_intervals = check_overlapping_intervals(outer_rows)
        if not overlapping_outer_intervals.empty:
            print(f"[{datetime.now():%H:%M:%S}] ({function_name}) {picam_id}: Overlapping intervals in '{outer_category}':\n{overlapping_outer_intervals}\n")

        # Validate `inner_category` rows
        inner_rows = ethogram_range[ethogram_range.index == inner_category]
        invalid_inner_order = check_frame_order(inner_rows)
        if not invalid_inner_order.empty:
            print(f"[{datetime.now():%H:%M:%S}] ({function_name}) {picam_id}: Invalid frame order in '{inner_category}':\n{invalid_inner_order}\n")

        overlapping_inner_intervals = check_overlapping_intervals(inner_rows)
        if not overlapping_inner_intervals.empty:
            print(f"[{datetime.now():%H:%M:%S}] ({function_name}) {picam_id}: Overlapping intervals in '{inner_category}':\n{overlapping_inner_intervals}\n")

        # Check that `inner_category` rows are within the preceding `outer_category` interval
        invalid_inner_within_outer = check_category_within_category(
            df=ethogram_range,
            outer_category=outer_category,
            inner_category=inner_category,
            start_col='start_frame',
            end_col='end_frame'
        )
        if not invalid_inner_within_outer.empty:
            print(f"[{datetime.now():%H:%M:%S}] ({function_name}) {picam_id}: '{inner_category}' rows outside their corresponding '{outer_category}' intervals:\n{invalid_inner_within_outer}\n")

    else:
        # General validation for configurations without specific categories
        invalid_frame_order = check_frame_order(ethogram_range)
        if not invalid_frame_order.empty:
            print(f"[{datetime.now():%H:%M:%S}] ({function_name}) {picam_id}: Invalid frame order:\n{invalid_frame_order}\n")

        overlapping_intervals = check_overlapping_intervals(ethogram_range)
        if not overlapping_intervals.empty:
            print(f"[{datetime.now():%H:%M:%S}] ({function_name}) {picam_id}: Overlapping intervals:\n{overlapping_intervals}\n")





def check_node_names(node_names, tracking_file):
    function_name = inspect.currentframe().f_code.co_name
    if "pup" in tracking_file:
        default_node_names = ['pup_head', 'pup_neck', 'pup_torso', 'pup_abdomen', 'pup_tailbase']
    elif "adult" in tracking_file:
        default_node_names = ['nose', 'head_center', 'left_ear', 'right_ear', 
                              'neck', 'left_side', 'body_center', 'right_side', 
                              'left_hip', 'right_hip', 'tailbase']
    else:
        return  # No known type
    
    differing_elements = [(elem1, elem2) for elem1, elem2 in zip(default_node_names, node_names) if elem1 != elem2]
    if differing_elements:
        print(f'[{datetime.now():%H:%M:%S}] ({function_name}) \033[38;5;208m\033[1mSpelling error in node names: {differing_elements} !!!\033[0m')


def print_tracking_metadata(tracking_file, locations, node_names):
    function_name = inspect.currentframe().f_code.co_name
    print(f'[{datetime.now():%H:%M:%S}] ({function_name}) Metadata for tracking file {os.path.basename(tracking_file)}')
    
    print("=== filename ===")
    print(tracking_file)
    print()
    
    print("=== locations data shape (frames * nodes * 2 (= x,y) * tracks) ===")
    print(locations.shape)
    print()
    
    print("=== enumerated nodes ===")
    nodes_dict = {name: ii for ii, name in enumerate(node_names)}
    print(nodes_dict)
    print()
    
    return nodes_dict


def load_SLEAP_tracking_data(homedir, expID, picam_id, animal_type):
    """
    Main function to load SLEAP tracking data for a specific animal type (pup or adult).
    Combines the search for the tracking file and loading the data.
    """
    function_name = inspect.currentframe().f_code.co_name
    tracking_path = f"{homedir}{expID}/01_picams/03_tracking/02_{picam_id}/03_SLEAP_files/"
    
    # Use animal_type (pup or adult) in the search string
    search_string = f'*_{animal_type}.predictions.analysis.h5'

    # Find tracking file
    tracking_file = ''.join(glob.glob(tracking_path + search_string))  # Convert list to string
    
    if os.path.exists(tracking_file):
        print(f'[{datetime.now():%H:%M:%S}] ({function_name}) Tracking data for {animal_type} found: {os.path.basename(tracking_file)}')
    else:
        print(f'[{datetime.now():%H:%M:%S}] ({function_name}) \033[38;5;208m\033[1mNo tracking data for {animal_type} found!\033[0m')
        return np.empty((0, 0, 0, 0)), {}

    # Load tracking data from the found file
    dataset_names, locations, node_names, track_names = load_tracking_data_from_file(tracking_file)
    
    # Check node names
    check_node_names(node_names, tracking_file)
    
    # Print metadata and return
    nodes_dict = print_tracking_metadata(tracking_file, locations, node_names)
    
    return locations, nodes_dict


def load_tracking_data_from_file(tracking_file):
    '''
    Load tracking data from the specified file.
    '''
    function_name = inspect.currentframe().f_code.co_name
    print(f'[{datetime.now():%H:%M:%S}] ({function_name}) Loading tracking data from file {os.path.basename(tracking_file)}')

    with h5py.File(tracking_file, "r") as f:
        dataset_names = list(f.keys())
        locations = f["tracks"][:].T
        node_names = [n.decode() for n in f["node_names"][:]]
        track_names = f['track_names'][:].T
        
    return dataset_names, locations, node_names, track_names



def find_LED_file(homedir, expID, picam_id):
    """
    Find the LED values file for a given experiment and picamera ID.
    """
    function_name = inspect.currentframe().f_code.co_name
    
    folder = homedir + expID + '/01_picams/01_raw/'
    fname = f'{expID}_{picam_id}_LEDvalues.csv'
    
    file_path = folder + fname
    if os.path.isfile(file_path):
        return file_path
    else:
        return None

def load_LED_data(file_path):
    """
    Load LED data from the CSV file.
    """
    picam_LEDsignal = pd.read_csv(file_path, header=[0], index_col=0, delimiter=',')
    return picam_LEDsignal

def preprocess_LED_data(picam_LEDsignal, picam_frames):
    """
    Preprocess the LED data (re-indexing, renaming, z-scoring, and adding frame times).
    Calls a helper function to detect blinks in the LED signal.
    """
    # Check if the number of rows in picam_LEDsignal matches the length of picam_frames
    if len(picam_LEDsignal) != len(picam_frames):
        raise ValueError(f"Mismatch in number of rows: picam_LEDsignal has {len(picam_LEDsignal)} rows, "
                         f"but picam_frames has {len(picam_frames)} entries. Ensure both inputs have the same length.")
    
    # Re-index such that the frame number starts at 0 and not at 1
    new_index       = picam_LEDsignal.index - 1
    picam_LEDsignal = picam_LEDsignal.set_index(new_index)
    picam_LEDsignal.index.rename('frame', inplace=True)

    # Rename column to 'LED_ROI_avg' and apply z-score
    picam_LEDsignal.columns = ['LED_ROI_avg']
    picam_LEDsignal         = picam_LEDsignal.apply(zscore)

    # Add frame time information from picam_frames
    picam_LEDsignal['frame_time_sec'] = picam_frames

    # Reorder columns
    cols            = ['frame_time_sec', 'LED_ROI_avg']
    picam_LEDsignal = picam_LEDsignal[cols]

    # Detect blinks and return both the processed signal and blink data
    blink_df = find_LED_blinks(picam_LEDsignal)
    
    return picam_LEDsignal, blink_df

def find_LED_blinks(df1):
    """
    Finds LED on and off frames in the LED_ROI intensity trace.
    Minimum peak distance is 7 frames.
    """
    x = np.abs(np.diff(df1['LED_ROI_avg'].to_numpy(), prepend=0))
    peaks, _ = find_peaks(x, distance=7, prominence=0.5)
    
    # Create a DataFrame with blink times and LED intensities at those frames
    blink_df = pd.DataFrame({
        'frame_time_sec': df1['frame_time_sec'].to_numpy()[peaks],
        'blinks': df1['LED_ROI_avg'].to_numpy()[peaks]
    })
    
    return blink_df


def load_picam_LED_data(homedir, expID, picam_id, picam_frames):
    """
    Main function to load, find, and preprocess LED data from a given picamera.

    Data represents the ROI, as seen by each picam, around a blinking 910nm LED controlled by an arduino board that is connected to a FP.  
    Pulse width as per arduino script should be 225ms (9 picam frames at 40fps), 
    interpulses are randomly chosen from interval [250ms, 525ms] (between 10 and 21 picam frames at 40 fps)
    
    """
    function_name = inspect.currentframe().f_code.co_name
    
    # Find the LED file
    file_path = find_LED_file(homedir, expID, picam_id)
    
    if file_path:
        # Load the LED data
        picam_LEDsignal = load_LED_data(file_path)
        
        # Preprocess the LED data
        picam_LEDsignal = preprocess_LED_data(picam_LEDsignal, picam_frames)
        print(f'[{datetime.now():%H:%M:%S}] ({function_name}) LED intensity values loaded!')
        
        return picam_LEDsignal
    else:
        # Return an empty list if no file is found
        print(f'[{datetime.now():%H:%M:%S}] ({function_name}) \033[38;5;208m\033[1mLED intensity values not found! Execute generate_LED_values_csv(exp) first.\033[0m')
        return []



def load_picam_pickle_file(homedir, expID):
    """
    Loads a pickle file for the given experiment, if it exists.
    """
    pickle_filepath = os.path.join(homedir, expID, '04_pickle_snapshots', f'{expID}_picam_dict.pickle')
    
    if os.path.exists(pickle_filepath):
        with open(pickle_filepath, 'rb') as f:
            return pickle.load(f)
    
    return None


def save_picam_pickle_file(homedir, expID, picam_dict):
    """
    Saves the given dictionary as a pickle file.

    Args:
        homedir (str): Base directory for the experiment.
        expID (str): Experiment ID.
        picam_dict (dict): Dictionary to save.
    """
    function_name = inspect.currentframe().f_code.co_name

    pickle_folder = os.path.join(homedir, expID, '04_pickle_snapshots')
    pickle_filepath = os.path.join(pickle_folder, f'{expID}_picam_dict.pickle')

    os.makedirs(pickle_folder, exist_ok=True)

    # Handle existing file
    if os.path.exists(pickle_filepath):
        existing_dict = load_picam_pickle_file(homedir, expID)
        if existing_dict:
            existing_status = existing_dict.get('picam_frame_analysis_run', None)
            new_status = picam_dict.get('picam_frame_analysis_run', None)

            if existing_status is False and new_status is True:
                print(f"\n[{datetime.now():%H:%M:%S}] ({function_name}) Overwriting existing file because 'picam_frame_analysis_run' is False in the existing file and True in the new dictionary.")
            else:
                print(f"\n[{datetime.now():%H:%M:%S}] ({function_name}) File already exists. Saving aborted.")
                return

    # Save the new file
    with open(pickle_filepath, 'wb') as f:
        pickle.dump(picam_dict, f, protocol=pickle.HIGHEST_PROTOCOL)

    print(f'\n[{datetime.now():%H:%M:%S}] ({function_name}) PICAM Data saved as pickle file!')
