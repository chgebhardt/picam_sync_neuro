#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Wed Oct 25 14:13:52 2023

@author: cgebhardt
"""

import os
from pathlib import Path

import sys
import re, socket
import shutil
import io
import yaml
import argparse

import datetime as dt
import time
from time import strftime

import picamera
import serial


#===========================================
# Functions and classes
#===========================================

def load_config(file_path):
    """
    Load configuration parameters from a YAML file
    """
    
    with open(file_path, 'r') as config_file:
        return yaml.safe_load(config_file)
    
    
def parse_and_load_config():
    """
    Parse command-line arguments and load configuration parameters from a YAML file.
    
    This function facilitates the use of a configuration file to parameterize scripts. It expects the name of a YAML
    configuration file as a command-line argument, and then it loads the configuration data from the specified file.
    
    Returns:
        dict: A dictionary containing the loaded configuration parameters.
    
    Raises:
        argparse.ArgumentError: If the 'config_file' argument is missing or if the specified file does not exist.
        yaml.YAMLError: If there is an issue with parsing the YAML file.
        FileNotFoundError: If the specified 'config_file' does not exist.
    """
    
    # Create an argument parser
    parser = argparse.ArgumentParser(description='Script to work with configuration parameters')

    # Add a command-line argument for the configuration file
    parser.add_argument('config_file', help='Path to the configuration file (YAML format)')

    # Parse the command-line arguments
    args = parser.parse_args()

    # Load the configuration from the specified file
    configuration_parameters = load_config(args.config_file)

    return configuration_parameters


def create_log_file(log_file_path=None):
    """
    Create a log file for writing and redirect standard output to the file.
    If log_file_path is not provided, use the default "log.out".
    """
    if log_file_path is None:
        log_file_path = "log.out"

    log_file   = open(log_file_path, "w")
    sys.stdout = log_file
    return log_file


def close_log_file(log_file):
    """
    Close the log file and restore standard output to the console.
    """
    sys.stdout = sys.__stdout__
    log_file.close()


def disk_usage(path="/"):
    """
    Check available disk space and stop the script if space is critically low.
    
    This function retrieves disk usage information for a specified path or the
    default root path. It then checks the amount of free disk space in gigabytes.
    If the free space falls below a critical threshold (10GB), the function prints
    a warning and terminates the script with a non-zero status code to indicate an error.
    
    Parameters:
    path (str, optional): The path for which to check disk usage. Default is the root path.
    
    Returns:
    None
    
    Example:
    disk_usage("/home/pi/data")
    """
    
    disk_info = shutil.disk_usage(path)
    free_GB = disk_info.free / 1e9
    print(f"\nThere are {free_GB:.2f} GB left on the disk at '{path}'")
    
    if free_GB < 10.0:
        print("There is less than 10GB of free space. Stopping the script.")
        sys.exit(1)  # Exit the script with a non-zero status code to indicate an error.
     
        
def create_experiment_folder(experimenter, exp_num, camera_num):
    """
    Create a new experiment folder for data storage.

    This function creates a new experiment folder with a specific structure
    for organizing and storing data related to behavioral experiments. It
    ensures that the folder does not already exist and then proceeds to
    create the necessary directory structure.

    Parameters:
    experimenter (str): The name of the experimenter conducting the experiment.
    exp_num (str): The experiment number or identifier.
    camera_num (list): A list of camera numbers used for the experiment.

    Returns:
    tuple: A tuple containing the experiment folder path and the experiment
    identifier.

    Example:
    exp_path, new_expID = create_experiment_folder("John Doe", "01", [1, 2])
    """
    
    # Create the root path
    root_path = Path('/home/pi/Desktop/Behavior') / experimenter

    # Create the experiment folder name
    currentDate = dt.datetime.now().strftime("%Y%m%d")
    new_expID   = f"{currentDate}_e{exp_num}_pic{camera_num[0]}"
    exp_path    = root_path / new_expID

    print(f'\nCreating new experiment folder for {new_expID}...')
    
    if exp_path.exists():
        print('Experiment folder already exists. Script aborted!')
        sys.exit()  # This is a hard exit without error collection
    else:
        exp_path.mkdir(parents=True, exist_ok=True)
        print('Folder created!')

    return (exp_path, new_expID)


def write_metadata(exp_path):
    """
    Create a metadata text file for experiment information.

    This function generates a text file containing metadata related to an
    experiment, including details such as the experimenter, animal ID, species,
    camera settings, and more. The text file is named after the experiment's
    unique identifier and is stored in the specified experiment path.

    Parameters:
    exp_path (str): The path where the metadata text file will be saved.

    Returns:
    None

    Example:
    write_metadata("/home/pi/experiments/experiment_01")
    """
    
    metadata = {
        'script_used': script_name,
        'experimenter': experimenter,
        'animalID': animalID,
        'speciesID': speciesID,
        'sex': sex,
        'repro_state': repro_state,
        'pup_age_days': pup_age_days,
        'litter': litter,
        'exp_num': exp_num,
        'camera_num': camera_num[0],
        'view': view,
        'illumination': illumination,
        'behavior_paradigm': behavior_paradigm,
        'photometry': photometry,
        'viral_injection_date': viral_injection_date,
        'virus_id': virus_id,
        'virus_target': virus_target,
        'video_duration_mins': video_duration_mins,
        'fps': FPS,
        'resolution_px': RESOLUTION_PX,
        'shutterspeed_us': SHUTTERSPEED_US,
        'bitrate': BITRATE
    }

    meta_fname      = f"{new_experimentID}.txt"
    metadata_lines  = [f"{new_experimentID}"]  # Include the expID identifier without key
    metadata_lines += [f"{key}:{value}" for key, value in metadata.items()]

    metadata_text = "\n".join(metadata_lines)

    try:
        with open(exp_path / meta_fname, "w") as file:
            file.write(metadata_text)
        print('\nTxt-file for Metadata created!')

    except Exception as e:
        print(f'\nCould not save txt-file for Metadata: {str(e)}')
    
    
class TimeStamp(object):
    """
    Class for issuing timestamps and saving them to CSV files.

    This class is designed for capturing timestamps from a picamera, specifically
    the PTS (from GPU) and pi STC, and saving them into CSV files. It can be
    used for video timestamp synchronization.

    Parameters:
    camera (Camera): The camera object providing frame data and timestamps.
    video_filename (str): The filename for the video output file.
    timestamp_filename (str): The filename for the CSV file to save timestamps.

    Methods:
    - write(buf): Write frame data and capture timestamps from the camera.
    - flush(): Save the captured timestamps to a CSV file.
    - close(): Close the video output file.

    Example:
    camera = Camera()
    timestamp = TimeStamp(camera, "video_output.mp4", "timestamps.csv")
    timestamp.write(frame_data)
    timestamp.flush()
    timestamp.close()
    """
    
    def __init__(self, camera, video_filename, timestamp_filename):
        self.camera         = camera
        self._video_output  = io.open(video_filename, 'wb')
        self._timestampFile = timestamp_filename
        self._timestamps    = []
        
    def write(self, buf):
        if self.camera.frame.complete is not None:
            if self.camera.frame.timestamp is None: # the first I-Frame and all SPS-Headers do not possess timestamps and are thus flagged with a timestamp of -1000 
               timestamp = -1000 
            else:
               timestamp = self.camera.frame.timestamp
            
            self._timestamps.append(
                ( self.camera.frame.index, self.camera.frame.frame_type, timestamp, time.time() )
                )
        
        return self._video_output.write(buf)
    
    def flush(self):
        with io.open(self._timestampFile, 'w') as f:
            f.write('index, frame_type, GPU Time, time.time()\n')
            for entry in self._timestamps:
                f.write('%d,%d,%d,%f\n' % entry)
        
    def close(self):
        self._video.close()
    

class Serializer:
    """
    Serial communication utility for camera control.
    
    This class provides a serial communication utility for controlling cameras
    connected to a Raspberry Pi. It can initialize a serial port, open and close
    the port, send data to the connected device, and receive data from it.
    
    Parameters:
    camera_num (list): A list containing the camera number(s) to determine the port.
    baudrate (int): The baud rate for serial communication (default: 115200).
    timeout (int): The communication timeout in seconds (default: 1).
    
    Methods:
    - open(): Open the serial port for communication.
    - close(): Close the serial port.
    - send(serial_msg): Send data to the connected device via the serial port.
    - receive(): Receive data from the connected device via the serial port.
    
    Example:
    camera1 = Serializer(['1'])
    camera1.open()
    camera1.send(b"StartRecording")
    received_data = camera1.receive()
    camera1.close()
    """

    def __init__(self, camera_num, baudrate=115200, timeout=1):
        self.camera_num = camera_num
        self.port = self._initialize_serial_port(baudrate, timeout)
    
    def _initialize_serial_port(self, baudrate, timeout):
        port = None
        if self.camera_num == ['1']:
            port = serial.Serial(port='/dev/ttyUSB0', baudrate=baudrate, timeout=timeout,
                                writeTimeout=timeout, parity=serial.PARITY_NONE,
                                stopbits=serial.STOPBITS_ONE, bytesize=serial.EIGHTBITS)
        elif self.camera_num == ['2']:
            port = serial.Serial(port='/dev/ttyS0', baudrate=baudrate, timeout=timeout,
                                writeTimeout=timeout, parity=serial.PARITY_NONE,
                                stopbits=serial.STOPBITS_ONE, bytesize=serial.EIGHTBITS)
        return port

    def open(self):
        ''' Open the serial port.'''
        if not self.port.is_open:
            self.port.open()

    def close(self):
        ''' Close the serial port.'''
        if self.port.is_open:
            self.port.close()

    def send(self, serial_msg):
        if self.port.is_open:
            self.port.write(bytes(serial_msg))
        else:
            print("Serial port is not open. Cannot send data.")

    def receive(self):
        if self.port.is_open:
            return self.port.read()
        else:
            print("Serial port is not open. Cannot receive data.")      


def RecordVideo(FPS, RESOLUTION_PX, SHUTTERSPEED_US, CAMERA_MODE, BITRATE):
    
    with picamera.PiCamera() as camera: 
      
        camera.resolution  = RESOLUTION_PX
        camera.framerate   = FPS
        camera.sensor_mode = CAMERA_MODE
        
        # preview while recording?
        if camera_preview and camera_num == ['2']:
           camera.start_preview(fullscreen = False, window = (400, 70, 640, 320))  
        
        # timestamp settings
        camera.annotate_background = picamera.Color('black')
        camera.annotate_text       = dt.datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')
        
        videoTime = strftime('%H%M%S')
        
        # create file names for videos
        videoName  = new_experimentID + '_' + videoTime + ".h264"
        path_video = os.path.join(experiment_path, videoName)
        
        if 'IR' in illumination:  
            
            camera.iso           = 300
            camera.shutter_speed = SHUTTERSPEED_US # in microseconds
            camera.awb_mode      = 'off'
            
            if camera_num == ['1']:
               rg , bg           = (0.8, 0.9) # automatic awb_mode is not working in NOIR picamera with firmware pre 07/2019!!!
            
            elif camera_num == ['2']:
               rg , bg           = (0.9, 0.85)
            
            camera.awb_gains     = (rg,bg) 
            camera.brightness    = 60               # [def 50,    0 100]
            camera.contrast      = 80               # [def  0, -100 100]
            
    
        elif 'RL' in illumination:
            camera.awb_mode = 'auto'
        
        output = TimeStamp(camera, path_video, os.path.join(experiment_path, new_experimentID + '_clock.csv'))
    
        camera.start_recording(output, format = 'h264', bitrate = BITRATE)  
        
        start = dt.datetime.now()
        while (dt.datetime.now() - start).seconds < video_duration_mins * 60:
            camera.annotate_text = dt.datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')                                     
            camera.annotate_text_size = 15
    
        camera.stop_recording()
        
        if camera_preview:
            camera.stop_preview()
                

def print_timestamp(message):
    """
    Print a timestamp along with a custom message.
    
    This function generates a timestamp and appends it to a custom message.
    The resulting message, which includes the current date and time in the format
    'YYYY-MM-DD HH:MM:SS.mmmmmm', is then printed to the console.
    
    Parameters:
    message (str): A custom message to be combined with the timestamp.
    
    Returns:
    None
    
    Example:
    print_timestamp("Starting the data collection")
    """
    
    timestamp = dt.datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')
    print(f'{message} {timestamp}')


def send_byte_run_acquistions(serial, camera_num, FPS, RESOLUTION_PX, SHUTTERSPEED_US, CAMERA_MODE, BITRATE):
    """
    Send a signal byte and start video acquisitions for the specified camera.
    
    This function sends a signal byte over a serial connection and initiates video
    acquisitions for the specified camera. Depending on the camera number, it either
    waits for a signal from another device to start recording [pic1] or sends a signal to
    commence the recording process [pic2]. Timestamps are provided to indicate the start and
    end times of video acquisitions.
    
    Parameters:
    serial (SerialConnection): A serial connection for communication.
    camera_num (list): A list containing the camera number(s) to determine the action.
    
    Returns:
    None
    
    Example:
    send_byte_run_acquisitions(serial_connection, ['1'])
    send_byte_run_acquisitions(serial_connection, ['2'])
    """

    if camera_num == ['1']:
        serial_msg = bytearray()
        print_timestamp('\nWaiting for message from rpi2...')
        
        while not serial_msg:
            serial_msg = ser.receive()
        
        if serial_msg:
            print_timestamp('\nRecording started at')
            
            RecordVideo(FPS, RESOLUTION_PX, SHUTTERSPEED_US, CAMERA_MODE, BITRATE)
            
            print_timestamp('Recording finished at')
    
    elif camera_num == ['2']:
        ser.send(1)
        print_timestamp('\nRecording started at')
        
        RecordVideo(FPS, RESOLUTION_PX, SHUTTERSPEED_US, CAMERA_MODE, BITRATE)
        
        print_timestamp('Recording finished at')



# MAIN CODE
if __name__ == '__main__':
   
    # get hostname / camera_number / script name (important because different parts of the script are run on different pis) 
    host        = socket.gethostname()     # extract hostname
    camera_num  = re.findall(r'\d+', host) # extract list of numberstr from string
    script_path = sys.argv[0]
    script_name = os.path.basename(script_path)

    #==========================================================================
    # Load Experiment Metadata from config.yaml file
    #==========================================================================

    # load config yaml file
    configuration_parameters = parse_and_load_config()
    
    # access the metadata parameters
    experimenter             = configuration_parameters['experimenter']
    animalID                 = configuration_parameters['animalID']
    speciesID                = configuration_parameters['speciesID']
    sex                      = configuration_parameters['sex']                 
    repro_state              = configuration_parameters['repro_state']
    pup_age_days             = configuration_parameters['pup_age_days']
    litter                   = configuration_parameters['litter']  
    exp_num                  = configuration_parameters['exp_num']
    beh_paradigm_id          = configuration_parameters['beh_paradigm_id']
    photometry               = configuration_parameters['photometry']
    viral_injection_date     = configuration_parameters['viral_injection_date']
    virus_id                 = configuration_parameters['virus_id']
    virus_target             = configuration_parameters['virus_target']


    # Define mappings for camera_num and beh_paradigm_id
    camera_num_mapping       = {'1': 'front', '2': 'top'}
    beh_paradigm_mapping     = {'pr': 'pup_retrieval', 'rm': 'retrieval_motivation'}

    # Use the mappings to transform the respective metadata values
    view                     = camera_num_mapping.get(camera_num[0], camera_num[0])
    behavior_paradigm        = beh_paradigm_mapping.get(beh_paradigm_id, beh_paradigm_id)

    #==========================================================================
    # Acquisition parameters
    #==========================================================================

    # set hard-coded recording parameters
    FPS                = 40          
    RESOLUTION_PX      = (1280,720)
    SHUTTERSPEED_US    = 3000            # shutter speed in microseconds
    CAMERA_MODE        = 6
    BITRATE            = 7000000          # video encoding bitrate (has an influence on dropped picam frames)

    # access variable recording parameters
    camera_preview      = configuration_parameters['camera_preview']
    illumination        = configuration_parameters['illumination']
    video_duration_mins = configuration_parameters['video_duration_mins']
    
    
    # Create a log file (using the default "log.out" if no path is provided)
    log_file = create_log_file('/home/pi/Desktop/logs/pic{}_log.out'.format(camera_num[0]))

    # Check available Diskspace
    disk_usage()

    # Create new experiment folder and save metadata file
    experiment_path, new_experimentID = create_experiment_folder(experimenter, exp_num, camera_num)
    
    # copy python script to experiment folder
    shutil.copy(__file__, str(experiment_path) + os.sep + os.path.basename(__file__)) 
    
    # Write metadata file to the experiment_path
    write_metadata(experiment_path)
    
    # serial port initialization (uses camera_num as list), send byte from rpi2 to rpi1 and acquistion start
    ser = Serializer(camera_num)
    
    send_byte_run_acquistions(ser, camera_num, FPS, RESOLUTION_PX, SHUTTERSPEED_US, CAMERA_MODE, BITRATE)
    
    ser.close()

    # Close the log file
    close_log_file(log_file)

    # copy log file to experiment folder
    shutil.copy(log_file.name, str(experiment_path) + os.sep + os.path.basename(log_file.name)) 
