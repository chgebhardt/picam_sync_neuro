# Standard Library Imports
import os
import glob
import inspect
import time
from datetime import datetime
from pathlib import Path

# Third-Party Libraries
import pandas as pd
import numpy as np


def load_daq_data(folder_path, expID):
    
    function_name = inspect.currentframe().f_code.co_name
    print(f'\n\n[{datetime.now():%H:%M:%S}] ({function_name}) Loading DAQ data for experiment {expID}')
    
    daq_dict = {'daq_timing': {}}

    # Define the daq data folder
    daq_folder = os.path.join(folder_path, expID, '02_daq')

    voltage_file = "daq_arduino_voltage.csv"
    voltage_path = os.path.join(daq_folder, voltage_file)
    
    if os.path.exists(voltage_path):
        arduino_voltage_df = pd.read_csv(voltage_path, dtype=np.float128)
        daq_dict['daq_timing']['arduino_voltage'] = arduino_voltage_df

        print(f'\n[{datetime.now():%H:%M:%S}] ({function_name}) Loaded: {voltage_file}')
    else:
        print("daq_arduino_voltage.csv not found in the folder.")
        print(f'\n[{datetime.now():%H:%M:%S}] ({function_name}) LED DAQ voltage file daq_arduino_voltage.csv not found in the folder!')
    
    return daq_dict