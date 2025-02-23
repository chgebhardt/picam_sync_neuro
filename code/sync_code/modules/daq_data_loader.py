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


def load_daq_data(homedir, expID, voltage_sampling_rate_Hz=3000, verbose=True):
    """
    Loads or initializes DAQ data for the given experiment. If a pickle file exists, it loads the data.
    Otherwise, it initializes a new DAQ data structure and optionally saves it as a pickle file.
    """
    function_name = inspect.currentframe().f_code.co_name
    print(f'\n\n[{datetime.now():%H:%M:%S}] ({function_name}) Loading DAQ data for experiment {expID}')

    # Attempt to load an existing pickle file
    daq_dict = load_daq_pickle_file(homedir, expID)
    if not daq_dict:
        # Initialize data structure
        daq_dict = initialize_daq_dict(homedir, expID, voltage_sampling_rate_Hz, verbose)

    else:
        print(f"\n[{datetime.now():%H:%M:%S}] ({function_name}) Found and loaded existing DAQ data previously saved on {daq_dict['daq_data_save_datetime']}!")

    # Print a summary of the loaded or newly created DAQ data
    print(f'\n[{datetime.now():%H:%M:%S}] ({function_name}) DAQ Acquisition SUMMARY:')
    print_daq_metadata_summary(daq_dict)

    return daq_dict

def initialize_daq_dict(homedir, expID, voltage_sampling_rate_Hz=3000, verbose=True):
    """
    Initializes the daq data dictionary from scratch if no pickle file exists.
    """
    function_name = inspect.currentframe().f_code.co_name
    
    # Define the daq data folder
    daq_folder = os.path.join(homedir, expID, '02_fp')

    # Initialize the dictionary
    daq_dict = {
        'expID': expID,
        'daq_data_save_datetime': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        'daq_frame_analysis_run': False, # set the 'daq frame analysis run' flag
        'daq_fluorescence_extraction_run': False # set the 'daq_fluorescence_normalization_run' flag
    }

    # Load (and preprocess) digital IOs
    digital_IOs, arduino_voltage_df, opto_pulse_train_timing = load_digital_IO_data(daq_folder, voltage_sampling_rate_Hz, daq_dict, verbose)
    
    # Save daq data in the dictionary
    daq_dict['daq_timing'] = {
        'digital_IOs': digital_IOs,
        'arduino_voltage': arduino_voltage_df,

    return daq_dict


def load_automated_opto_stimulation_settings(fp_folder):
    """
    Finds and loads the stimulation settings file from the specified folder.
    
    Parameters:
        fp_folder (str): Path to the folder containing the CSV file.
    
    Returns:
        pd.DataFrame: The loaded stimulation settings DataFrame or None if no file exists.
    """
    # Find the stimulation settings file
    csv_files = glob.glob(os.path.join(fp_folder, "stimulation_settings_*.csv"))
    
    if not csv_files:
        return None  # File does not exist
    
    # Load the file into a DataFrame
    stimulation_file = csv_files[0]
    settings_df = pd.read_csv(stimulation_file, delimiter=';', index_col=0)
    
    # Print a success message
    function_name = inspect.currentframe().f_code.co_name
    print(f'\n[{datetime.now():%H:%M:%S}] ({function_name}) Automated stimulation parameters found and loaded!')
    
    return settings_df


def load_and_process_fp_calibration_file(fp_folder):
    """
    Loads the fp_calibration_*.csv file with a semicolon delimiter, extracts metadata from the first three rows, 
    and processes the remaining data into a multilevel DataFrame.
    
    Parameters:
        fp_folder (str): Path to the folder containing the calibration CSV file.
    
    Returns:
        dict: A dictionary with keys `date`, `fiber_diameter`, `power_meter_model`, 
              and `calibration_values_df`. Returns an empty dictionary if no valid file is found.
    """

    function_name = inspect.currentframe().f_code.co_name
    
    # Find the calibration file
    calibration_file = next((f for f in glob.glob(os.path.join(fp_folder, "fp_calibration_*.csv"))), None)
    if not calibration_file:
        # Print a failure message if no file is found
        print(f'\n[{datetime.now():%H:%M:%S}] ({function_name}) \033[38;5;208m\033[1mNo FP power calibration file found!\033[0m')
        return {}  # Return empty dictionary   
    
    # Read metadata from the first three lines and discard unnecessary columns
    metadata = {}
    with open(calibration_file, 'r') as file:
        for line in [file.readline().strip() for _ in range(3)]:
            key_value = line.split(';')[0].split(':', 1)
            if len(key_value) == 2:
                metadata[key_value[0].strip()] = key_value[1].strip()
    
    # Check if required metadata keys are present
    required_keys = ['date', 'fiber_diameter', 'power_meter_model']
    if not all(key in metadata for key in required_keys):
        return {}  # Return empty dictionary if required metadata keys are missing
    
    # Load calibration data starting from the 5th row
    calibration_values_df = pd.read_csv(calibration_file, skiprows=4, header=[0, 1], delimiter=';')

    # Print a success message
    print(f"\n[{datetime.now():%H:%M:%S}] ({function_name}) FP power calibration file from \033[38;5;208m\033[1m{metadata.get('date')}\033[0m found and loaded!")
    
    # Return the results
    return {
        'date': metadata.get('date'),
        'fiber_diameter': metadata.get('fiber_diameter'),
        'power_meter_model': metadata.get('power_meter_model'),
        'calibration_values': calibration_values_df if not calibration_values_df.empty else pd.DataFrame()
    }
    

def load_fp_metadata(fp_folder, xml_file, fp_opto_laser_parameter_df=None):
    '''
    Loads FP metadata from an XML configuration file, automatically detecting the format (new or old).
    If fp_opto_laser_parameter_df is provided and not empty, it updates the "OptoStimulation" key with unique values.\
    The Emission data is extracted from the fp_fluorescence_raw_data DataFrame for the FP3002Configuration format.
    '''
    
    # Create filepath to xml file
    xml_file_path = os.path.join(fp_folder, xml_file)
    
    # Parse XML data
    tree = ET.parse(xml_file_path)
    root = tree.getroot()
    
    # Initialize metadata dictionary
    metadata = {}

    # Check which format the XML file corresponds to by checking for unique tags
    if root.tag == "Settings":
        # New XML format (XML with Excitation and OptoStimulation)
        metadata = {
            "Excitation": {
                "TriggerPeriod_Hz": float(root.find('.//Excitation/TriggerPeriod').text.split()[0]),
                "Sequence": [
                    {led.text.strip(): (int(led.get('Index')), int(led.get('Flag')))}  # Use LED name as the key
                    for led in root.findall('.//Excitation/Sequence/LED')
                ],
                "Power_perc": {
                    power_tag.tag: float(power_tag.text.strip('%'))  # Use the tag name (LED name) as key
                    for power_tag in root.findall('.//Excitation/Power/*')
                }
            },
            "OptoStimulation": {
                "LaserWavelength_nm": [float(root.find('.//OptoStimulation/LaserWavelength').text)],
                "LaserAmplitude_perc": [float(root.find('.//OptoStimulation/LaserAmplitude').text.strip('%'))],
                "StimulusFrequency_Hz": [float(root.find('.//OptoStimulation/StimPeriod').text.split()[0])],
                "PulseWidth_sec": [float(root.find('.//OptoStimulation/StimOn').text.split()[0]) / 1000],  # Convert to seconds
                "Number_of_pulses": [int(root.find('.//OptoStimulation/StimReps').text)]
            },
            "Emission": {
                "green": [
                    f"fiber{i}" for i, region in enumerate(root.findall('.//Emission/Region')) 
                    if region.text.startswith('G')
                ],
                "red": [
                    f"fiber{i}" for i, region in enumerate(root.findall('.//Emission/Region')) 
                    if region.text.startswith('R')
                ]
            }
        }

        # If fp_opto_laser_parameter_df exists and is not empty, update OptoStimulation key
        if fp_opto_laser_parameter_df is not None and not fp_opto_laser_parameter_df.empty:
            metadata["OptoStimulation"] = {
                "LaserAmplitude_perc": fp_opto_laser_parameter_df['LaserAmplitude_perc'].unique().tolist(),
                "StimulusFrequency_Hz": fp_opto_laser_parameter_df['StimulusFrequency_Hz'].unique().tolist(),
                "PulseWidth_sec": (fp_opto_laser_parameter_df['PulseWidth_ms'] / 1000).unique().tolist(),
                "Number_of_pulses": fp_opto_laser_parameter_df['Number_of_pulses'].unique().tolist()
            }
        
    elif root.tag == "FP3002Configuration":
        # Old XML format (FP3002Config.xml)
        metadata = {
            "Excitation": {
                # In the old XML, 'FrameRate' is used as 'TriggerPeriod_Hz'
                "TriggerPeriod_Hz": float(root.find('.//FrameRate').text) if root.find('.//FrameRate') is not None else None,
                
                "Sequence": [
                    {led.text.strip(): (None, None)}  # Each LED is now a dictionary with (None, None)
                    for led in root.findall('.//TriggerState/Trigger')
                ],
                "Power_perc": {
                    "L415": (float(root.find('.//L415').text) - 9600) / 256,  # Normalize LED power percentage
                    "L470": (float(root.find('.//L470').text) - 9600) / 256,
                    "L560": (float(root.find('.//L560').text) - 9600) / 256
                }
            },
            # Add the 'Emission' key based on the dataframe
            "Emission": {}
        }

        # read raw fluorescence data (this is where they stored the Region number and descriptions
        fp_fluorescence_raw_data_file_old_firmware = os.path.join(fp_folder, 'fp_full_data.csv')
        fp_fluorescence_raw_data                   = pd.read_csv(fp_fluorescence_raw_data_file_old_firmware, index_col=0)

        # Now, we'll populate the 'Emission' field using fp_fluorescence_raw_data_old_firmware if provided
        if fp_fluorescence_raw_data is not None:
            # Extracting the columns that contain 'RegionG' and 'RegionR' from the DataFrame
            green_fibers = [f"fiber{i}" for i in range(8) if f"Region{i}G" in fp_fluorescence_raw_data.columns]
            red_fibers   = [f"fiber{i}" for i in range(8) if f"Region{i}R" in fp_fluorescence_raw_data.columns]

            metadata["Emission"] = {
                "green": green_fibers,
                "red": red_fibers
            }

    else:
        raise ValueError("Unknown XML format!")

    return metadata


def print_fp_metadata_summary(fp_dict):
    """
    Prints a summary of the loaded FP metadata and FP data.
    """
    
    # Get the current function name using inspect
    func_name = inspect.currentframe().f_code.co_name

    # Extract metadata from fp_dict
    fp_metadata = fp_dict.get('fp_metadata', {})
    fp_timing   = fp_dict.get('fp_timing', {})
    
    # Ensure metadata keys are available before printing
    if 'Emission' in fp_metadata:
        emission_metadata = fp_metadata['Emission']
        print('\n            Fibers found: {}'.format(emission_metadata))
            
    if 'Excitation' in fp_metadata:
        excitation_metadata = fp_metadata['Excitation']
        
        # Print LED names instead of the entire sequence
        led_names = [led_name for led in excitation_metadata.get('Sequence', []) for led_name in led.keys()]
        print('            LEDs found: {}'.format(led_names))
        
        # Print other metadata with integer values
        total_fps = excitation_metadata.get('TriggerPeriod_Hz', 'N/A')
        print('            total FP framerate [fps]: {}'.format(int(total_fps) if total_fps != 'N/A' else 'N/A'))
        
        # Calculate and print FP framerate per LED channel as an integer
        num_leds = len(excitation_metadata.get('Sequence', []))
        if num_leds > 0 and total_fps != 'N/A':
            framerate_per_led = total_fps / num_leds
            print('            FP framerate per LED channel [fps]: {}'.format(int(framerate_per_led)))
        
        # Loop through each LED and its power percentage
        for led_name, power_perc in excitation_metadata.get('Power_perc', {}).items():
            print(f'            {led_name} power [%]: {power_perc}')
    
    
    # Check for 'OptoStimulation' key in fp_metadata
    if 'OptoStimulation' in fp_metadata:
        # Print the "Optostimulation data found!" statement in orange (close to yellow) and bold
        print(f'\n            \033[1;38;5;214mOptostimulation data found!\033[0m')

        for key, value in fp_dict['fp_metadata']['OptoStimulation'].items():
            print(f"            {key}: {value}")
    else:
        print(f'\n            \033[1;38;5;214mNo optostimulation data found!\033[0m')
    

def load_digital_IO_data(fp_folder, voltage_sampling_rate_Hz, fp_dict, verbose):
    """
    Automatically detects and processes digital IO data files based on their version (old or new firmware).
    Args:
        fp_folder (str): Path to the folder containing digital IO files.
        voltage_sampling_rate_Hz (int): Sampling rate for the voltage data.
        verbose (bool): Whether to print detailed processing information.
    Returns:
        tuple: (digital_IO_channels, arduino_voltage_df) processed data.
    """
        
    function_name = inspect.currentframe().f_code.co_name
    
    # Detect file version based on filenames
    old_file = next((f for f in os.listdir(fp_folder) if 'fp_arduino_ttl.csv' in f), None)
    new_file = next((f for f in os.listdir(fp_folder) if 'fp_digital_IOs.csv' in f), None)

    # Load data based on file type
    if old_file:
        file_path = os.path.join(fp_folder, old_file)
        print(f"[{datetime.now():%H:%M:%S}] ({function_name}) Detected \033[38;5;208m\033[1mold FP3002 firmware\033[0m file: {old_file}")
        digital_IO_data = load_digitalIO_data_old_firmware(file_path)
    
    elif new_file:
        file_path = os.path.join(fp_folder, new_file)
        print(f"[{datetime.now():%H:%M:%S}] ({function_name}) Detected \033[38;5;208m\033[1mnew FP3002 firmware\033[0m file for digitalIOs: {new_file}")
        digital_IO_data = load_digitalIO_data_new_firmware(file_path)
    
    else:
        raise FileNotFoundError(f"No recognized digital IO data files found in {fp_folder}.")

    # Split the channels and process the data
    digital_IO_channels = split_digital_IO_channels(digital_IO_data)

    # Process the data from Input0 (= blinking LED)  
    arduino_voltage_df  = process_Input0(fp_folder, digital_IO_channels, voltage_sampling_rate_Hz, verbose)

    # Process Optostimulation Data (laser pulses etc) and adds data from automated stimulation parameter changes
    opto_pulse_train_timing  = process_Output1(digital_IO_channels, fp_dict)
    
    # Log results
    function_name = inspect.currentframe().f_code.co_name
    unique_items = digital_IO_data['DigitalIOName'].unique()
    print(f'\n[{datetime.now():%H:%M:%S}] ({function_name}) Digital IO channel data from {unique_items} successfully loaded!')

    return digital_IO_channels, arduino_voltage_df, opto_pulse_train_timing


def load_digitalIO_data_old_firmware(file_path):
    """
    Loads and preprocesses digital IO data from old firmware files.
    Args:
        file_path (str): Path to the old firmware file.
    Returns:
        pd.DataFrame: Processed digital IO data.
    """
    
    return pd.read_csv(
        file_path,
        header = None,
        names = ['fp_time_sec', 'edge', 'bonsai_time_msec']
    ).drop(columns=['bonsai_time_msec']).assign(DigitalIOName='Input0')


def load_digitalIO_data_new_firmware(file_path):
    """
    Loads and preprocesses digital IO data from new firmware files.
    Args:
        file_path (str): Path to the new firmware file.
    Returns:
        pd.DataFrame: Processed digital IO data.
    """
    return pd.read_csv(file_path).rename(columns={
        'SystemTimestamp': 'fp_time_sec',
        'DigitalIOState': 'edge',
    }).rename_axis('event_number')


def process_Input0(fp_folder, digital_IO_channels, voltage_sampling_rate_Hz, verbose):
    """
    Processes 'Input0' channel data if present.
    
    Input0 represents the rising and falling edges of the voltage making an 910nm LED blink 
    as received from an arduino board that is connected to the FP 
    Pulse width as per arduino script should be 225ms (9 picam frames at 40fps), 
    interpulses are randomly chosen from interval [250ms, 525ms] (between 10 and 21 picam frames at 40 fps)
    
    Args:
        fp_folder (str): Path to the folder containing digital IO files.
        digital_IO_channels (dict): Split digital IO data by channel.
        voltage_sampling_rate_Hz (int): Sampling rate for voltage data.
        verbose (bool): Whether to print detailed processing information.
    Returns:
        pd.DataFrame or None: Processed voltage data for 'Input0' or None if not applicable.
    """
    if 'Input0' not in digital_IO_channels:
        return None

    function_name = inspect.currentframe().f_code.co_name
    print(f'\n[{datetime.now():%H:%M:%S}] ({function_name}) Pre-processing Input0 (=arduino LED flips)')
    
    digital_IO_channels['Input0'] = preprocess_Input0(digital_IO_channels['Input0'], verbose)
    
    return load_arduino_voltage(fp_folder, digital_IO_channels['Input0'], voltage_sampling_rate_Hz)

    
def split_digital_IO_channels(digital_IO_data):
    '''Splits the digital IO dataframe into separate dataframes based on 'Item1.DigitalIOFlag' values.'''
  
    digital_IO_split = {}
    for flag, group in digital_IO_data.groupby('DigitalIOName'):
        digital_IO_split[flag] = group

    return digital_IO_split


def find_missing_flips(arduino2fp_flips, verbose):
    '''Finds missing flips and returns a list of tuples (index, edge, fp_time_sec)'''
    
    # Find missing flips (list of tuples containing index, edge, and fp_time_sec)
    missing_flips = arduino2fp_flips[arduino2fp_flips['edge'].diff() == 0].index.tolist()
    missing_flips = [(index, 1 - arduino2fp_flips.loc[index, 'edge'], arduino2fp_flips.loc[index, 'fp_time_sec']) 
                    for index in missing_flips]
    
    return missing_flips

def preprocess_Input0(arduino2fp_flips, verbose):
    '''Pre-processes digital_IO_channels['Input0'] by handling edge cases and missing flips'''

    # Drop respective rows if first flip is a falling edge (==0) or last row is a rising edge (==1)
    if arduino2fp_flips.loc[0, 'edge'] == 0:
        arduino2fp_flips.drop(arduino2fp_flips.head(1).index, inplace=True)
        arduino2fp_flips.index = arduino2fp_flips.index - arduino2fp_flips.index[0]  # re-indexing
        if verbose:
            print(f'[{datetime.now():%H:%M:%S}] ({inspect.currentframe().f_code.co_name}) first pulse incomplete, first falling edge removed from Input0!')
    
    if arduino2fp_flips.loc[arduino2fp_flips.index[-1], 'edge'] == 1:
        arduino2fp_flips.drop(arduino2fp_flips.tail(1).index, inplace=True)
        if verbose:
            print(f'[{datetime.now():%H:%M:%S}] ({inspect.currentframe().f_code.co_name}) last pulse incomplete, last rising edge removed from Input0!')

    # Find missing flips using the updated function
    missing_flips = find_missing_flips(arduino2fp_flips, verbose)
    
    # Insert missing flips if any
    arduino2fp_flips = insert_missing_flips(arduino2fp_flips, missing_flips)

    # Only print if there were missed flips
    if verbose and missing_flips:
        print(f'[{datetime.now():%H:%M:%S}] ({inspect.currentframe().f_code.co_name}) Missing flips found before flip (flip index, up or down, fp_time_s): {missing_flips}')
        print(f'[{datetime.now():%H:%M:%S}] ({inspect.currentframe().f_code.co_name}) Flip(s) inserted!')

    return arduino2fp_flips

def insert_missing_flips(arduino2fp_flips, missing_flips):
    '''Insert missing flips into the arduino2fp_flips DataFrame based on the provided missing_flips'''
    
    # Create a new DataFrame to insert the missing flips
    for index, flip_identity, fp_time_sec in missing_flips:
        if flip_identity == 0:  # Falling edge
            falling_timepoint = arduino2fp_flips.loc[index - 1, 'fp_time_sec'] + 0.22515
            line = pd.DataFrame({"fp_time_sec": falling_timepoint, "edge": 0}, index=[index])
            arduino2fp_flips = pd.concat([arduino2fp_flips.iloc[:index], line, arduino2fp_flips.iloc[index:]], ignore_index=False)
        
        elif flip_identity == 1:  # Rising edge
            rising_timepoint = arduino2fp_flips.loc[index, 'fp_time_sec'] - 0.22515
            line = pd.DataFrame({"fp_time_sec": rising_timepoint, "edge": 1}, index=[index])
            arduino2fp_flips = pd.concat([arduino2fp_flips.iloc[:index+1], line, arduino2fp_flips.iloc[index+1:]], ignore_index=False)
    
    return arduino2fp_flips

def load_arduino_voltage(folder, arduino2fp_flips, voltage_sampling_rate_Hz):
    '''
    Retrieve or generate Arduino voltage data for Input0.

    Parameters:
        folder (str): The directory path where the voltage data file is stored or will be saved.
        arduino2fp_flips (ndarray): A NumPy array containing two columns: 'fp_time_sec' and 'edge' timepoints for Arduino flips.
        voltage_sampling_rate_Hz (float): The sampling rate of the voltage signal in Hertz.

    Returns:
        tuple: A tuple containing:
            - `time_range` (ndarray): The time vector corresponding to the voltage data.
            - `arduino_voltage` (ndarray): The Arduino voltage signal generated from the flip times.
    
    If the voltage data file exists in the specified folder, it is loaded. Otherwise, the voltage signal is 
    generated from the provided edge timepoints and saved as a CSV file.
    '''
    
    # Get the current function name using inspect
    func_name = inspect.currentframe().f_code.co_name

    # Define the voltage file path
    voltage_file = os.path.join(folder, f'fp_arduino_voltage_{int(voltage_sampling_rate_Hz)}.csv')
    
    # Check if the voltage data file exists
    if os.path.isfile(voltage_file):
        print(f'[{datetime.now():%H:%M:%S}] ({func_name}) fp_arduino_voltage_{int(voltage_sampling_rate_Hz)}.csv already exists! Loading...')
        
        tic = time.time()
        # Load the voltage data from the CSV file

        # Load the voltage data into a DataFrame with headers
        arduino_voltage_df = pd.read_csv(voltage_file, delimiter=',')
        
        toc = time.time()
        
        print(f'[{datetime.now():%H:%M:%S}] ({func_name}) Done! {round(toc - tic, 1)} seconds elapsed.')

    else:
        print(f'[{datetime.now():%H:%M:%S}] ({func_name}) fp_arduino_voltage_{int(voltage_sampling_rate_Hz)}.csv not found, generating arduino_voltage from arduino2fp_flips...')
        
        tic = time.time()

        # Generate the voltage signal arduino_voltage from the edge timepoints
        time_range, arduino_voltage = generate_arduino_voltage_file(arduino2fp_flips, voltage_sampling_rate_Hz)

        # Save arduino_voltage as CSV
        print(f'[{datetime.now():%H:%M:%S}] ({func_name}) Saving arduino_voltage as fp_arduino_voltage_{int(voltage_sampling_rate_Hz)}.csv...')
        
        # Save using numpy savetxt
        np.savetxt(voltage_file, np.column_stack((time_range, arduino_voltage)) , delimiter=',', header='fp_time_sec,voltage', comments='')

        arduino_voltage_df = pd.DataFrame({'fp_time_sec': time_range, 'voltage': arduino_voltage})
        
        toc = time.time()
        
        print(f'[{datetime.now():%H:%M:%S}] ({func_name}) Done! {round(toc - tic, 1)} seconds elapsed')

    return arduino_voltage_df

def generate_arduino_voltage_file(arduino2fp_flips, voltage_sampling_rate_Hz):
    '''
    Reconstitutes arduino_voltage from the timepoints of Arduino TTL edges as recorded by the FP on DigitalIn.
    The signal is generated at the given sampling rate (in Hz).
    
    Note: The function's running time scales almost linearly with voltage_sampling_rate_Hz.     
    '''
    
    # Ensure the time column is numeric, converting if necessary
    if isinstance(arduino2fp_flips, pd.DataFrame):
        fp_time_sec = pd.to_numeric(arduino2fp_flips['fp_time_sec'], errors='coerce').values
    else:
        fp_time_sec = arduino2fp_flips[:, 0]  # Assuming arduino2fp_flips is now a numpy array with two columns [fp_time_sec, edge]
    
    # Create a time vector from the first to the last flip, with the given sampling rate
    start_time = fp_time_sec[0]
    end_time = fp_time_sec[-1]
    
    # Ensure both start_time and end_time are float (if they were strings, they are now converted)
    time_range = np.arange(float(start_time), float(end_time) + 1 / voltage_sampling_rate_Hz, 1 / voltage_sampling_rate_Hz)
    
    # Initialize the voltage array, initially set to 0
    arduino_voltage = np.zeros_like(time_range)
    
    # Extract rising and falling edge timepoints
    if isinstance(arduino2fp_flips, pd.DataFrame):
        rise = arduino2fp_flips.query('edge == 1')['fp_time_sec'].values
        fall = arduino2fp_flips.query('edge == 0')['fp_time_sec'].values
    else:
        rise = arduino2fp_flips[arduino2fp_flips[:, 1] == 1, 0]
        fall = arduino2fp_flips[arduino2fp_flips[:, 1] == 0, 0]

    # Find the indices of the closest timepoints for both rising and falling edges
    rise_indices = np.searchsorted(time_range, rise)
    fall_indices = np.searchsorted(time_range, fall) - 1
    
    # Set the voltage to 1 between each rising and falling edge
    for rise_idx, fall_idx in zip(rise_indices, fall_indices):
        arduino_voltage[rise_idx:fall_idx+1] = 1  # +1 to include the falling edge
    
    # Return the result as a structured array (if you still need time data)
    return time_range, arduino_voltage


def process_Output1(digital_IO_channels, fp_dict):
    """
    Processes 'Output1' channel data if present.
    
    Output1 represents the rising and falling edges denoting laser pulses
    Pulse width is determined by PulseWidth_sec in the FP metadata, 
    interpulses are determined by 1/StimulusFrequency_Hz minus PulseWidth_sec 
    
    Args:
        fp_folder (str): Path to the folder containing digital IO files.
        digital_IO_channels (dict): Split digital IO data by channel.
        voltage_sampling_rate_Hz (int): Sampling rate for vooutput1_df, pulse_train_timingltage data.
        verbose (bool): Whether to print detailed processing information.
    Returns:
        pd.DataFrame or None: Processed voltage data for 'Input0' or None if not applicable.
    """
    if 'Output1' not in digital_IO_channels:
        return None

    function_name = inspect.currentframe().f_code.co_name
    print(f'\n[{datetime.now():%H:%M:%S}] ({function_name}) Pre-processing digital Output1 (= opto laser pulses)')
    
    digital_IO_channels['Output1'], opto_pulse_train_timing = preprocess_Output1(digital_IO_channels['Output1'], fp_dict)
    
    return opto_pulse_train_timing
    
def preprocess_Output1(output1_df, fp_dict):
    '''Pre-processes digital_IO_channels['Output1'] to handle edge cases and missing flips'''
    
    # Calculate the time differences between consecutive 'fp_time_sec' values
    output1_df['fp_time_diff_sec'] = output1_df['fp_time_sec'].diff()

    # Create a boolean mask where (fp_time_diff > 1/StimulusFrequency_Hz) is met, this will catch all cases if there are no timing issues 
    # as the temporal difference between differen pulse trains will always be much longer than the period of the signal (1/Freq)
    stim_freq_hz = fp_dict['fp_metadata']['OptoStimulation']['StimulusFrequency_Hz'][0]
    mask         = output1_df['fp_time_diff_sec'] > 1 / stim_freq_hz  
    
    # Use cumsum to increment the pulse train index whenever the condition is met
    output1_df.loc[:, 'pulse_train_index'] = mask.cumsum()

    # Find inconsistencies in the laser pulses (different number of pulses per pulse train than requested, consecutive up or down edges
    # (instead of True / up followed by a False / down, incoherent timing of pulses)
    #pulses = opto_check_laser_pulse_consistency(output1_df, fp_dict) 

    # Group by 'index' and aggregate to get the first and last 'fp_time_sec' in each group
    pulse_train_timing = output1_df.groupby('pulse_train_index').agg(start_stim_fp_sec=('fp_time_sec', 'first'), 
                                                                     end_stim_fp_sec=('fp_time_sec', 'last'))

    return output1_df, pulse_train_timing

def opto_check_laser_pulse_consistency(df, fp_dict):
    
    # Get the function name for the log message
    function_name = inspect.currentframe().f_code.co_name
    
    # Extract relevant parameters from fp_dict
    stim_freq_hz   = fp_dict['fp_metadata']['OptoStimulation']['StimulusFrequency_Hz']
    pulse_width_sec = round(fp_dict['fp_metadata']['OptoStimulation']['PulseWidth_sec'], 3)
    num_pulses     = fp_dict['fp_metadata']['OptoStimulation']['Number_of_pulses']
    
    # Threshold values for checking deviations
    expected_true_diff  = np.round(1 / stim_freq_hz - pulse_width_sec, 4)
    expected_false_diff = pulse_width_sec
    
    # Iterate through the dataframe and check for inconsistencies
    pulse_train_counts = df.groupby('pulse_train_index').size()

    # Store all the inconsistencies found
    all_inconsistencies = []

    # Print analyzing message
    print(f"[{datetime.now():%H:%M:%S}] ({function_name}) Analyzing opto laser pulses for experiment {fp_dict['expID']}!")
    
    for pulse_train_index, edge_count in pulse_train_counts.items():
        inconsistencies = []
        first_row_index = df[df['pulse_train_index'] == pulse_train_index].index.min()
        last_row_index  = df[df['pulse_train_index'] == pulse_train_index].index.max()

        # Check if the pulse train count is too large 
        if edge_count > num_pulses * 2:
            inconsistencies.append(f"  * {int(edge_count / 2)} pulses found, {num_pulses} pulses expected")
        
        # Check for inconsistencies within the pulse train
        for ii in range(1, len(df)):
            if df.iloc[ii]['pulse_train_index'] == pulse_train_index:
                # Check for successive True or False
                if df.iloc[ii]['edge'] == df.iloc[ii - 1]['edge']:
                    inconsistencies.append(f"  * Successive {df.iloc[ii]['edge']} at index {df.index[ii-1]} and {df.index[ii]}")

                # Check the fp_time_diff_sec for 'True' values
                if df.iloc[ii]['edge'] == True:
                    # Skip the first row of each pulse train (first_row_index)
                    if df.index[ii] == first_row_index:
                        continue  # Skip to the next iteration if it's the first row
                    
                    if not np.isnan(df.iloc[ii]['fp_time_diff_sec']):
                        diff = df.iloc[ii]['fp_time_diff_sec']
                        # Check if the diff is within the expected range
                        if not (expected_true_diff - 0.0005 < diff < expected_true_diff + 0.0005):
                            inconsistencies.append(f"  * True row with fp_time_diff_sec {diff} at index {df.index[ii]}")

                # Check the fp_time_diff_sec for 'False' values
                if df.iloc[ii]['edge'] == 'False':
                    diff = df.iloc[ii]['fp_time_diff_sec']
                    if not (expected_false_diff - 0.0005 < diff < expected_false_diff + 0.0005):
                        inconsistencies.append(f"  * False row with fp_time_diff_sec {diff} at index {df.index[ii]}")

        # If there are any inconsistencies, format the output
        if inconsistencies:
            all_inconsistencies.append(f"\nlaser pulse train #{pulse_train_index} ({first_row_index} - {last_row_index}):")
            all_inconsistencies.extend(inconsistencies)
    
    # Print all the inconsistencies found
    if all_inconsistencies:
        print(f"\n[{datetime.now():%H:%M:%S}] ({function_name}) Inconsistent opto laser pulse trains detected:")
        print("\n".join(all_inconsistencies))
    else:
        print(f"[{datetime.now():%H:%M:%S}] ({function_name}) \033[38;5;208m\033[1mNo opto laser pulse train timing inconsistencies found!\033[0m")

    return all_inconsistencies
    

def load_fluorescence_data(expID, fp_folder, fp_dict):
    '''Loads the full FP data (fluorescence data) from the CSV file.'''

    fps = int(fp_dict['fp_metadata']['Excitation']['TriggerPeriod_Hz'])
    
    fp_interleaved_data_file = os.path.join(fp_folder, 'fp_full_data.csv')
    fp_interleaved_data      = pd.read_csv(fp_interleaved_data_file, index_col=0)

    fp_interleaved_data.rename(columns={'FrameCounter': 'fp_frame', 'SystemTimestamp': 'fp_time_sec', 'Timestamp':'fp_time_sec'}, inplace=True)

    if 'LedState' in fp_interleaved_data.columns:
        fp_interleaved_data = fp_interleaved_data.rename(columns = {'LedState': 'Flags'})

    # delete the first 10s of each recording (=> due to either fast bleaching or LED power drop on startup)
    fp_interleaved_data = fp_interleaved_data.iloc[fps*10:, :]
    
    function_name = inspect.currentframe().f_code.co_name
    print(f'\n[{datetime.now():%H:%M:%S}] ({function_name}) Fluorescence FP data loaded!')

    return fp_interleaved_data


def add_laser_stimulation_parameters_to_pulse_train_timing(fp_dict, opto_pulse_train_timing, fp_opto_laser_parameter_df):
    """
    Adds all columns from the stimulation settings DataFrame to opto_pulse_train_timing cyclically.
    If the DataFrame does not exist or is empty, it uses data from fp_dict['fp_metadata']['OptoStimulation'].

    Parameters:
        opto_pulse_train_timing (pd.DataFrame): The main DataFrame to which columns will be added.
        fp_opto_laser_parameter_df (pd.DataFrame or None): The stimulation settings DataFrame.
        fp_dict (dict): Dictionary containing metadata for fallback if the DataFrame is missing or empty.

    Returns:
        pd.DataFrame: Updated opto_pulse_train_timing with added columns.
    """
    # If the DataFrame exists and is not empty, add its data cyclically
    if fp_opto_laser_parameter_df is not None and not fp_opto_laser_parameter_df.empty:
        for column in fp_opto_laser_parameter_df.columns:
            values = fp_opto_laser_parameter_df[column].to_list()
            num_values = len(values)
            # Repeat cyclically for the length of opto_pulse_train_timing
            opto_pulse_train_timing[column] = [values[i % num_values] for i in range(len(opto_pulse_train_timing))]
        return opto_pulse_train_timing

    # Fallback: Use data from fp_dict['fp_metadata']['OptoStimulation']
    opto_stimulation = fp_dict.get('fp_metadata', {}).get('OptoStimulation', {})

    # Add data from the metadata to the DataFrame
    for column, values in opto_stimulation.items():
        num_values = len(values)
        # Repeat cyclically for the length of opto_pulse_train_timing
        opto_pulse_train_timing[column] = [values[i % num_values] for i in range(len(opto_pulse_train_timing))]

    return opto_pulse_train_timing


def map_amplitude_to_laser_power(opto_pulse_train_timing, fp_calibration_data_dict):
    """
    Maps 'Amplitude_%' to 'laser635nm_uW' in the opto_pulse_train_timing dataframe.

    Parameters:
        opto_pulse_train_timing (DataFrame): DataFrame containing stimulation timing data.
        fp_calibration_data_dict (dict): Dictionary containing calibration data.

    Returns:
        DataFrame: Updated DataFrame with 'laser635nm_uW' column. If calibration data is missing or invalid,
                   returns the original dataframe unmodified.
    """
    # Check if the calibration data dictionary exists and contains the expected structure
    if (
        not isinstance(fp_calibration_data_dict, dict) or 
        'calibration_values' not in fp_calibration_data_dict or 
        'FIBER1' not in fp_calibration_data_dict['calibration_values']
    ):
        return opto_pulse_train_timing  # Return unmodified dataframe if calibration data is missing or invalid

    # Extract the calibration dataframe
    calibration_df = fp_calibration_data_dict['calibration_values']['FIBER1']
    
    # Create a dictionary for quick lookup of 'LED/laser power_%' to 'laser635nm_uW'
    lookup_dict = dict(zip(calibration_df['LED/laser power_%'], calibration_df['laser635nm_uW']))
    
    # Map the 'Amplitude_%' values from opto_pulse_train_timing to 'laser635nm_uW'
    opto_pulse_train_timing['laser635nm_uW'] = opto_pulse_train_timing['LaserAmplitude_perc'].map(lookup_dict)
    
    # If no match, the result will be NaN, which is the desired behavior
    return opto_pulse_train_timing



def load_fp_pickle_file(homedir, expID):
    """
    Loads a pickle file for the given experiment, if it exists.
    """
    pickle_filepath = os.path.join(homedir, expID, '04_pickle_snapshots', f'{expID}_fp_dict.pickle')
    
    if os.path.exists(pickle_filepath):
        with open(pickle_filepath, 'rb') as f:
            return pickle.load(f)
    
    return None


def save_fp_pickle_file(homedir, expID, fp_dict):
    """
    Saves the given dictionary as a pickle file.

    Args:
        homedir (str): Base directory for the experiment.
        expID (str): Experiment ID.
        fp_dict (dict): Dictionary to save.
    """
    function_name = inspect.currentframe().f_code.co_name

    pickle_folder = os.path.join(homedir, expID, '04_pickle_snapshots')
    pickle_filepath = os.path.join(pickle_folder, f'{expID}_fp_dict.pickle')

    os.makedirs(pickle_folder, exist_ok=True)

    # Handle existing file
    if os.path.exists(pickle_filepath):
        existing_dict = load_fp_pickle_file(homedir, expID)
        if existing_dict:
            existing_fp_frame_status = existing_dict.get('fp_frame_analysis_run', None)
            existing_fp_fluorescence_status = existing_dict.get('fp_fluorescence_extraction_run', None)
            new_fp_frame_status = fp_dict.get('fp_frame_analysis_run', None)
            new_fp_fluorescence_status = fp_dict.get('fp_fluorescence_extraction_run', None)

            if (existing_fp_frame_status is False and new_fp_frame_status is True) or \
               (existing_fp_fluorescence_status is False and new_fp_fluorescence_status is True):
                print(f"\n[{datetime.now():%H:%M:%S}] ({function_name}) Overwriting existing file because one or more analysis flags are False in the existing fp_dict.pickle file and True in the new fp_dict.")
            else:
                print(f"\n[{datetime.now():%H:%M:%S}] ({function_name}) File already exists. Saving aborted.")
                return

    # Save the new file
    with open(pickle_filepath, 'wb') as f:
        pickle.dump(fp_dict, f, protocol=pickle.HIGHEST_PROTOCOL)

    print(f'\n[{datetime.now():%H:%M:%S}] ({function_name}) FP Data saved as pickle file!')