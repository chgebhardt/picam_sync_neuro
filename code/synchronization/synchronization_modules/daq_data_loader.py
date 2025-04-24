# Necessary Standard Library Imports
import os
from datetime import datetime

# Third-Party Libraries
import pandas as pd
import numpy as np
from scipy.signal import find_peaks

def load_daq_data(folder_path, expID, daq_frequency):
    """
    Load DAQ (Data Acquisition) data for a given experiment ID from the specified folder.
    
    This function retrieves the Arduino voltage trace recorded during an experiment,
    processes it to detect rising and falling edges, and returns a dictionary containing
    the relevant DAQ timing data.
    
    Parameters:
    -----------
    folder_path : str
        Path to the main experiment folder.
    expID : str
        Experiment identifier used to locate specific data.
    daq_frequency : float
        Sampling frequency of the DAQ system in Hz.
    
    Returns:
    --------
    dict
        A dictionary containing the loaded DAQ data:
        - 'daq_timing': A dictionary with the following keys:
            - 'arduino_voltage_df': DataFrame containing raw voltage traces.
            - 'arduino2daq_edges_df': DataFrame containing detected rising and falling edges.
    """
    function_name = "load_daq_data"
    print(f'\n\n[{datetime.now():%H:%M:%S}] ({function_name}) Loading DAQ data for experiment {expID}')
    
    daq_dict = {'daq_timing': {}}

    # Define the DAQ data folder
    daq_folder   = os.path.join(folder_path, expID, '02_daq')
    voltage_file = "daq_arduino_voltage.csv"
    voltage_path = os.path.join(daq_folder, voltage_file)
    
    if os.path.exists(voltage_path):
        arduino_voltage_df                           = pd.read_csv(voltage_path)
        daq_dict['daq_timing']['arduino_voltage_df'] = arduino_voltage_df

        print(f'\n[{datetime.now():%H:%M:%S}] ({function_name}) Loaded: {voltage_file}')

        print(f'\n[{datetime.now():%H:%M:%S}] ({function_name}) Searching for rising and falling edges of the daq_arduino_voltage signal...')
        daq_dict['daq_timing']['arduino2daq_edges_df'] = find_arduino_edges(arduino_voltage_df, daq_frequency)
        
    else:
        print(f'\n[{datetime.now():%H:%M:%S}] ({function_name}) LED DAQ voltage file {voltage_file} not found in the folder!')
    
    return daq_dict


def find_arduino_edges(df, daq_frequency):
    '''
    Finds arduino edges (rising and falling) in the arduino_voltage trace.
    Minimum peak distance is 0.200s * daq_frequency (arduinio pulse duration is 0.225s, cf /code/arduino/random_blinking_LED_generator.ino).
    '''
    x        = np.abs(np.diff(df['voltage'].to_numpy(), prepend=0))
    peaks, _ = find_peaks(x, distance=0.175*daq_frequency, prominence=0.5)
    
    # Create a DataFrame with edge times and LED intensities at those frames
    edge_df = pd.DataFrame({
        'daq_time_sec': df['daq_time_sec'].to_numpy()[peaks],
        'edges': df['voltage'].to_numpy()[peaks]
    })
    
    return edge_df
