# Standard Library Imports
from datetime import datetime
import inspect
import os
import re

# Third-Party Libraries
import numpy as np
import pandas as pd
from scipy.stats import zscore
from scipy.signal import find_peaks


def load_picam_data(homedir, expID, verbose=True):
    """
    Detects how many picams there are and creates a nested dictionary for each camera.
    """
    function_name = inspect.currentframe().f_code.co_name
    print(f'[{datetime.now():%H:%M:%S}] ({function_name}) Loading PiCamera data for experiment {expID}')

    # Initialize data structure
    picam_list = find_picams(homedir, expID)
    picam_dict = initialize_picam_dict(homedir, expID, picam_list)

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
    Initializes the picam dictionary.
    """
    function_name = inspect.currentframe().f_code.co_name
    
    picam_dict = {
        'expID': expID,
        'picam_data_generated_datetime': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        'picam_list': picam_list,
    }

    for picam_id in picam_list:

        # Load metadata
        picam_metadata = load_picam_metadata(homedir, expID, picam_id)
        if not picam_metadata:
            print(f'[{datetime.now():%H:%M:%S}] ({function_name}) No metadata found for picam ID: {picam_id}. Skipping.')
            continue

        # Load and process frame time data
        frame_df = load_picamera_clock_data(homedir, expID, picam_id)
        if frame_df is None:
            print(f'[{datetime.now():%H:%M:%S}] ({function_name}) No frame timing data found for picam ID: {picam_id}. Skipping.')
            continue

        # Load LED blink data
        picam_LEDsignal, picam_LED_blinks = load_picam_LED_data(homedir, expID, picam_id, frame_df['GPU_time_sec'].values)
        
        # Graceful handling if LED data is None
        if picam_LEDsignal is None or picam_LED_blinks is None:
            picam_LEDsignal = []  # or None, depending on your preference
            picam_LED_blinks = []  # or None, depending on your preference
        
        # Store timing data
        picam_timing = {
            'picam_frame_info': frame_df,
            'picam_LEDsignal':  picam_LEDsignal,
            'picam_LED_blinks': picam_LED_blinks
        }

        # Populate picam_dict
        picam_dict[picam_id] = {
            'picam_metadata':  picam_metadata,
            'picam_timing':    picam_timing
        }

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

    Data represents the ROI, as seen by each picam, around a blinking 910nm LED controlled by an arduino board that is connected to a DAQ board.  
    Pulse width as per arduino script should be 225ms (9 picam frames at 40fps), 
    interpulses are randomly chosen from interval [250ms, 525ms] (between 10 and 21 picam frames at 40 fps)
    """
    function_name = inspect.currentframe().f_code.co_name
    
    # Find the LED file
    file_path = find_LED_file(homedir, expID, picam_id)
    
    if file_path:
        # Load the LED data
        picam_LEDsignal = load_LED_data(file_path)
        
        # Preprocess the LED data and detect blinks
        picam_LEDsignal, picam_LED_blinks = preprocess_LED_data(picam_LEDsignal, picam_frames)
        
        print(f'[{datetime.now():%H:%M:%S}] ({function_name}) LED intensity values loaded!')
        
        return picam_LEDsignal, picam_LED_blinks  # Return both variables
    else:
        # Return None for both if no file is found
        print(f'[{datetime.now():%H:%M:%S}] ({function_name}) \033[38;5;208m\033[1mLED intensity values not found! Run project_initiation.ipynb first.\033[0m')
        return None, None  # Return None for both
