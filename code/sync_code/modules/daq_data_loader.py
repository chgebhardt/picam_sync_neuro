# Standard Library Imports
import os
import pickle
import glob
import inspect
import time
from datetime import datetime
import xml.etree.ElementTree as ET
from pathlib import Path

# Third-Party Libraries
import pandas as pd
import numpy as np

def load_daq_data(folder_path, expID):
    
    # Attempt to load an existing pickle file
    daq_dict = load_daq_pickle_file(folder_path, expID)
    
    if not daq_dict:
        # Initialize data structure
        # daq_dict = initialize_daq_dict(folder_path, expID, voltage_sampling_rate_Hz, verbose)
        daq_dict = {}

        # Define the daq data folder
        daq_folder = os.path.join(folder_path, expID, '02_daq')
    
        daq_dict = {'daq_timing': {}}
        # Search for files in the specified folder
        voltage_file    = None
        digital_io_file = None
        
        for file in os.listdir(daq_folder):
            if file.startswith("daq_arduino_voltage_") and file.endswith(".csv"):
                voltage_file = file
            elif file == "daq_digital_IOs.csv":
                digital_io_file = file
        
        # Load voltage file if it exists
        if voltage_file:
            voltage_path       = os.path.join(daq_folder, voltage_file)
            arduino_voltage_df = pd.read_csv(voltage_path)
            
            daq_dict['daq_timing']['arduino_voltage'] = arduino_voltage_df
            print(f"Loaded: {voltage_file}")
        
        elif digital_io_file:
            # Load digital IO file only if voltage file does not exist
            digital_io_path = os.path.join(daq_folder, digital_io_file)
            digital_io_df   = pd.read_csv(digital_io_path)
            
            daq_dict['daq_timing']['digital_IO'] = digital_io_df
            print(f"Loaded: {digital_io_file}")
        else:
            print("No relevant DAQ files found in the folder.")
    
    return daq_dict



# def load_daq_data(homedir, expID, voltage_sampling_rate_Hz=3000, verbose=True):
#     """
#     Loads or initializes DAQ data for the given experiment. If a pickle file exists, it loads the data.
#     Otherwise, it initializes a new DAQ data structure and optionally saves it as a pickle file.
#     """
#     function_name = inspect.currentframe().f_code.co_name
#     print(f'\n\n[{datetime.now():%H:%M:%S}] ({function_name}) Loading DAQ data for experiment {expID}')

#     # Attempt to load an existing pickle file
#     daq_dict = load_daq_pickle_file(homedir, expID)
#     if not daq_dict:
#         # Initialize data structure
#         daq_dict = initialize_daq_dict(homedir, expID, voltage_sampling_rate_Hz, verbose)

#     else:
#         print(f"\n[{datetime.now():%H:%M:%S}] ({function_name}) Found and loaded existing DAQ data previously saved on {daq_dict['daq_data_save_datetime']}!")

#     return daq_dict


def initialize_daq_dict(homedir, expID, voltage_sampling_rate_Hz=3000, verbose=True):
    """
    Initializes the daq data dictionary from scratch if no pickle file exists.
    """
    function_name = inspect.currentframe().f_code.co_name
    
    # Define the daq data folder
    daq_folder = os.path.join(homedir, expID, '02_daq')

    # Initialize the dictionary
    daq_dict = {
        'expID': expID,
        'daq_data_save_datetime': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }

    # Load (and preprocess) digital IOs
    digital_IOs, arduino_voltage_df = load_digital_IO_data(daq_folder, voltage_sampling_rate_Hz, daq_dict, verbose)
    
    # Save daq data in the dictionary
    daq_dict['daq_timing'] = {
        'digital_IOs': digital_IOs,
        'arduino_voltage': arduino_voltage_df,
    }

    return daq_dict


def load_digital_IO_data(daq_folder, voltage_sampling_rate_Hz, daq_dict, verbose):
    """
    Automatically detects and processes digital IO data files based on their version (old or new firmware).
    Args:
        daq_folder (str): Path to the folder containing digital IO files.
        voltage_sampling_rate_Hz (int): Sampling rate for the voltage data.
        verbose (bool): Whether to print detailed processing information.
    Returns:
        tuple: (digital_IO_channels, arduino_voltage_df) processed data.
    """
        
    function_name = inspect.currentframe().f_code.co_name
    
    
    file_path       = os.path.join(daq_folder, new_file)
    digital_IO_data = load_digitalIO_data(file_path)
    
    # Split the channels and process the data
    digital_IO_channels = split_digital_IO_channels(digital_IO_data)

    # Process the data from Input0 (= blinking LED)  
    arduino_voltage_df  = process_Input0(daq_folder, digital_IO_channels, voltage_sampling_rate_Hz, verbose)
    
    # Log results
    function_name = inspect.currentframe().f_code.co_name
    unique_items = digital_IO_data['DigitalIOName'].unique()
    print(f'\n[{datetime.now():%H:%M:%S}] ({function_name}) Digital IO channel data from {unique_items} successfully loaded!')

    return digital_IO_channels, arduino_voltage_df


def load_digitalIO_data(file_path):
    """
    Loads and preprocesses digital IO data from new firmware files.
    Args:
        file_path (str): Path to the new firmware file.
    Returns:
        pd.DataFrame: Processed digital IO data.
    """
    return pd.read_csv(file_path).rename(columns={
        'SystemTimestamp': 'daq_time_sec',
        'DigitalIOState': 'edge',
    }).rename_axis('event_number')


def process_Input0(daq_folder, digital_IO_channels, voltage_sampling_rate_Hz, verbose):
    """
    Processes 'Input0' channel data if present.
    
    Input0 represents the rising and falling edges of the voltage making an 910nm LED blink 
    as received from an arduino board that is connected to the DAQ 
    Pulse width as per arduino script should be 225ms (9 picam frames at 40fps), 
    interpulses are randomly chosen from interval [250ms, 525ms] (between 10 and 21 picam frames at 40 fps)
    
    Args:
        daq_folder (str): Path to the folder containing digital IO files.
        digital_IO_channels (dict): Split digital IO data by channel.
        voltage_sampling_rate_Hz (int): Sampling rate for voltage data.
        verbose (bool): Whether to print detailed processing information.
    Returns:
        pd.DataFrame or None: Processed voltage data for 'Input0' or None if not applicable.
    """
    if 'Input0' not in digital_IO_channels:
        return None

    function_name = inspect.currentframe().f_code.co_name
    print(f'\n[{datetime.now():%H:%M:%S}] ({function_name}) Pre-processing Input0 (=arduino LED edges)')
    
    digital_IO_channels['Input0'] = preprocess_Input0(digital_IO_channels['Input0'], verbose)
    
    return load_arduino_voltage(daq_folder, digital_IO_channels['Input0'], voltage_sampling_rate_Hz)

    
def split_digital_IO_channels(digital_IO_data):
    '''Splits the digital IO dataframe into separate dataframes based on 'Item1.DigitalIOFlag' values.'''
  
    digital_IO_split = {}
    for flag, group in digital_IO_data.groupby('DigitalIOName'):
        digital_IO_split[flag] = group

    return digital_IO_split


def find_missing_edges(arduino2daq_edges, verbose):
    '''Finds missing edges and returns a list of tuples (index, edge, daq_time_sec)'''
    
    # Find missing edges (list of tuples containing index, edge, and daq_time_sec)
    missing_edges = arduino2daq_edges[arduino2daq_edges['edge'].diff() == 0].index.tolist()
    missing_edges = [(index, 1 - arduino2daq_edges.loc[index, 'edge'], arduino2daq_edges.loc[index, 'daq_time_sec']) 
                    for index in missing_edges]
    
    return missing_edges

def preprocess_Input0(arduino2daq_edges, verbose):
    '''Pre-processes digital_IO_channels['Input0'] by handling edge cases and missing edgess'''

    # Drop respective rows if first edges is a falling edge (==0) or last row is a rising edge (==1)
    if arduino2daq_edges.loc[0, 'edge'] == 0:
        arduino2daq_edges.drop(arduino2daq_edges.head(1).index, inplace=True)
        arduino2daq_edges.index = arduino2daq_edges.index - arduino2daq_edges.index[0]  # re-indexing
        if verbose:
            print(f'[{datetime.now():%H:%M:%S}] ({inspect.currentframe().f_code.co_name}) first pulse incomplete, first falling edge removed from Input0!')
    
    if arduino2daq_edges.loc[arduino2daq_edges.index[-1], 'edge'] == 1:
        arduino2daq_edges.drop(arduino2daq_edges.tail(1).index, inplace=True)
        if verbose:
            print(f'[{datetime.now():%H:%M:%S}] ({inspect.currentframe().f_code.co_name}) last pulse incomplete, last rising edge removed from Input0!')

    # Find missing edges using the updated function
    missing_edges = find_missing_edges(arduino2daq_edges, verbose)
    
    # Insert missing edges if any
    arduino2daq_edges = insert_missing_edges(arduino2daq_edges, missing_edges)

    # Only print if there were missed edges
    if verbose and missing_edges:
        print(f'[{datetime.now():%H:%M:%S}] ({inspect.currentframe().f_code.co_name}) Missing edges found before edge (edge index, up or down, daq_time_s): {missing_edges}')
        print(f'[{datetime.now():%H:%M:%S}] ({inspect.currentframe().f_code.co_name}) Edge(s) inserted!')

    return arduino2daq_edges

def insert_missing_edges(arduino2daq_edges, missing_edges):
    '''Insert missing edges into the arduino2daq_edges DataFrame based on the provided missing_edges'''
    
    # Create a new DataFrame to insert the missing edges
    for index, edge_identity, daq_time_sec in missing_edges:
        if edge_identity == 0:  # Falling edge
            falling_timepoint = arduino2daq_edges.loc[index - 1, 'daq_time_sec'] + 0.22515
            line = pd.DataFrame({"daq_time_sec": falling_timepoint, "edge": 0}, index=[index])
            arduino2daq_edges = pd.concat([arduino2daq_edges.iloc[:index], line, arduino2daq_edges.iloc[index:]], ignore_index=False)
        
        elif edge_identity == 1:  # Rising edge
            rising_timepoint = arduino2daq_edges.loc[index, 'daq_time_sec'] - 0.22515
            line = pd.DataFrame({"daq_time_sec": rising_timepoint, "edge": 1}, index=[index])
            arduino2daq_edges = pd.concat([arduino2daq_edges.iloc[:index+1], line, arduino2daq_edges.iloc[index+1:]], ignore_index=False)
    
    return arduino2daq_edges

def load_arduino_voltage(folder, arduino2daq_edges, voltage_sampling_rate_Hz):
    '''
    Retrieve or generate Arduino voltage data for Input0.

    Parameters:
        folder (str): The directory path where the voltage data file is stored or will be saved.
        arduino2daq_edges (ndarray): A NumPy array containing two columns: 'daq_time_sec' and 'edge' timepoints for Arduino edges.
        voltage_sampling_rate_Hz (float): The sampling rate of the voltage signal in Hertz.

    Returns:
        tuple: A tuple containing:
            - `time_range` (ndarray): The time vector corresponding to the voltage data.
            - `arduino_voltage` (ndarray): The Arduino voltage signal generated from the edge times.
    
    If the voltage data file exists in the specified folder, it is loaded. Otherwise, the voltage signal is 
    generated from the provided edge timepoints and saved as a CSV file.
    '''
    
    # Get the current function name using inspect
    func_name = inspect.currentframe().f_code.co_name

    # Define the voltage file path
    voltage_file = os.path.join(folder, f'daq_arduino_voltage_{int(voltage_sampling_rate_Hz)}.csv')
    
    # Check if the voltage data file exists
    if os.path.isfile(voltage_file):
        print(f'[{datetime.now():%H:%M:%S}] ({func_name}) daq_arduino_voltage_{int(voltage_sampling_rate_Hz)}.csv already exists! Loading...')
        
        tic = time.time()
        # Load the voltage data from the CSV file

        # Load the voltage data into a DataFrame with headers
        arduino_voltage_df = pd.read_csv(voltage_file, delimiter=',')
        
        toc = time.time()
        
        print(f'[{datetime.now():%H:%M:%S}] ({func_name}) Done! {round(toc - tic, 1)} seconds elapsed.')

    else:
        print(f'[{datetime.now():%H:%M:%S}] ({func_name}) daq_arduino_voltage_{int(voltage_sampling_rate_Hz)}.csv not found, generating arduino_voltage from arduino2fdaq_edges...')
        
        tic = time.time()

        # Generate the voltage signal arduino_voltage from the edge timepoints
        time_range, arduino_voltage = generate_arduino_voltage_file(arduino2daq_edges, voltage_sampling_rate_Hz)

        # Save arduino_voltage as CSV
        print(f'[{datetime.now():%H:%M:%S}] ({func_name}) Saving arduino_voltage as daq_arduino_voltage_{int(voltage_sampling_rate_Hz)}.csv...')
        
        # Save using numpy savetxt
        np.savetxt(voltage_file, np.column_stack((time_range, arduino_voltage)) , delimiter=',', header='daq_time_sec,voltage', comments='')

        arduino_voltage_df = pd.DataFrame({'daq_time_sec': time_range, 'voltage': arduino_voltage})
        
        toc = time.time()
        
        print(f'[{datetime.now():%H:%M:%S}] ({func_name}) Done! {round(toc - tic, 1)} seconds elapsed')

    return arduino_voltage_df

def generate_arduino_voltage_file(arduino2daq_edges, voltage_sampling_rate_Hz):
    '''
    Reconstitutes arduino_voltage from the timepoints of Arduino TTL edges as recorded by the DAQ on DigitalIn.
    The signal is generated at the given sampling rate (in Hz).
    
    Note: The function's running time scales almost linearly with voltage_sampling_rate_Hz.     
    '''
    
    # Ensure the time column is numeric, converting if necessary
    if isinstance(arduino2daq_edges, pd.DataFrame):
        daq_time_sec = pd.to_numeric(arduino2daq_edges['daq_time_sec'], errors='coerce').values
    else:
        daq_time_sec = arduino2daq_edges[:, 0]  # Assuming arduino2daq_edges is now a numpy array with two columns [daq_time_sec, edge]
    
    # Create a time vector from the first to the last edge, with the given sampling rate
    start_time = daq_time_sec[0]
    end_time   = daq_time_sec[-1]
    
    # Ensure both start_time and end_time are float (if they were strings, they are now converted)
    time_range = np.arange(float(start_time), float(end_time) + 1 / voltage_sampling_rate_Hz, 1 / voltage_sampling_rate_Hz)
    
    # Initialize the voltage array, initially set to 0
    arduino_voltage = np.zeros_like(time_range)
    
    # Extract rising and falling edge timepoints
    if isinstance(arduino2daq_edges, pd.DataFrame):
        rise = arduino2daq_edges.query('edge == 1')['daq_time_sec'].values
        fall = arduino2daq_edges.query('edge == 0')['daq_time_sec'].values
    else:
        rise = arduino2daq_edges[arduino2daq_edges[:, 1] == 1, 0]
        fall = arduino2daq_edges[arduino2daq_edges[:, 1] == 0, 0]

    # Find the indices of the closest timepoints for both rising and falling edges
    rise_indices = np.searchsorted(time_range, rise)
    fall_indices = np.searchsorted(time_range, fall) - 1
    
    # Set the voltage to 1 between each rising and falling edge
    for rise_idx, fall_idx in zip(rise_indices, fall_indices):
        arduino_voltage[rise_idx:fall_idx+1] = 1  # +1 to include the falling edge
    
    # Return the result as a structured array (if you still need time data)
    return time_range, arduino_voltage


def load_daq_pickle_file(homedir, expID):
    """
    Loads a pickle file for the given experiment, if it exists.
    """
    pickle_filepath = os.path.join(homedir, expID, '04_pickle_snapshots', f'{expID}_daq_dict.pickle')
    
    if os.path.exists(pickle_filepath):
        with open(pickle_filepath, 'rb') as f:
            return pickle.load(f)
    
    return None


def save_daq_pickle_file(homedir, expID, daq_dict):
    """
    Saves the given dictionary as a pickle file.

    Args:
        homedir (str): Base directory for the experiment.
        expID (str): Experiment ID.
        daq_dict (dict): Dictionary to save.
    """
    function_name = inspect.currentframe().f_code.co_name

    pickle_folder = os.path.join(homedir, expID, '04_pickle_snapshots')
    pickle_filepath = os.path.join(pickle_folder, f'{expID}_daq_dict.pickle')

    os.makedirs(pickle_folder, exist_ok=True)

    # Handle existing file
    if os.path.exists(pickle_filepath):
        existing_dict = load_daq_pickle_file(homedir, expID)
        if existing_dict:
            existing_daq_frame_status = existing_dict.get('daq_frame_analysis_run', None)
            existing_daq_fluorescence_status = existing_dict.get('daq_fluorescence_extraction_run', None)
            new_daq_frame_status = daq_dict.get('daq_frame_analysis_run', None)
            new_daq_fluorescence_status = daq_dict.get('daq_fluorescence_extraction_run', None)

            if (existing_daq_frame_status is False and new_daq_frame_status is True) or \
               (existing_daq_fluorescence_status is False and new_daq_fluorescence_status is True):
                print(f"\n[{datetime.now():%H:%M:%S}] ({function_name}) Overwriting existing file because one or more analysis flags are False in the existing daq_dict.pickle file and True in the new daq_dict.")
            else:
                print(f"\n[{datetime.now():%H:%M:%S}] ({function_name}) File already exists. Saving aborted.")
                return

    # Save the new file
    with open(pickle_filepath, 'wb') as f:
        pickle.dump(daq_dict, f, protocol=pickle.HIGHEST_PROTOCOL)

    print(f'\n[{datetime.now():%H:%M:%S}] ({function_name}) DAQ Data saved as pickle file!')