import shutil
import os
import sys
import re
import socket
import datetime as dt

from picam_acquisition_modules import config, logging, experiment_manager, serial_pi_comm, utils

if __name__ == '__main__':
    """
    Main script for PiCamera acquisition.

    This script:
    - Loads configuration from `config.yaml`
    - Detects camera number from hostname
    - Sets up logging and checks disk space
    - Creates an experiment folder and saves metadata
    - Initializes serial communication between Raspberry Pis
    - Starts the video acquisition process
    - Closes resources and saves logs
    """

    # ==========================================================================
    # SYSTEM IDENTIFICATION & CONFIGURATION LOADING
    # ==========================================================================

    # Identify Raspberry Pi hostname and extract camera number from it
    host = socket.gethostname()  
    camera_num = re.findall(r'\d+', host)  # Extract numeric part from hostname (e.g., "picam1" → ['1'])

    # Get script name
    script_name = os.path.basename(sys.argv[0])  

    # Load configuration from YAML
    configuration_parameters = config.parse_config_and_load()

    # Update configuration with dynamically detected parameters
    configuration_parameters.update({
        'camera_num': camera_num,
        'script_name': script_name
    })

    # Define mappings for camera view and behavioral paradigms
    camera_num_mapping = {'1': 'front', '2': 'top'}
    beh_paradigm_mapping = {'pr': 'pup_retrieval', 'rm': 'retrieval_motivation'}

    # Map values based on configuration
    configuration_parameters['view'] = camera_num_mapping.get(camera_num[0], camera_num[0])
    configuration_parameters['behavior_paradigm'] = beh_paradigm_mapping.get(
        configuration_parameters['beh_paradigm_id'], 
        configuration_parameters['beh_paradigm_id']
    )

    # ==========================================================================
    # ACQUISITION PARAMETERS (HARDCODED)
    # ==========================================================================

    # These parameters are hardcoded because some PiCamera settings are fixed
    HARD_CODED_PARAMETERS = {
        'FPS': 40,
        'RESOLUTION_PX': (1280, 720),
        'SHUTTERSPEED_US': 3000,  # Microseconds
        'CAMERA_MODE': 6,
        'BITRATE': 7000000  # Affects dropped frames
    }

    # Add hardcoded parameters to the configuration
    configuration_parameters.update(HARD_CODED_PARAMETERS)

    # ==========================================================================
    # SYSTEM SETUP (LOGGING, STORAGE, DISK CHECK)
    # ==========================================================================

    # Create a log file (one per camera)
    log_file = logging.create_log_file(f'/home/pi/Desktop/logs/pic{camera_num[0]}_log.out')

    # Check available disk space (script exits if too low)
    utils.disk_usage()

    # ==========================================================================
    # EXPERIMENT SETUP (FOLDER CREATION & METADATA)
    # ==========================================================================

    # Create a new experiment folder and get its ID
    experiment_path, new_experimentID = experiment_manager.create_experiment_folder(configuration_parameters)

    # Copy this script to the experiment folder with a timestamped filename
    script_backup_name = f"{dt.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}_main.py"
    shutil.copy(__file__, os.path.join(experiment_path, script_backup_name))

    # Save metadata file in the experiment folder
    experiment_manager.write_metadata(experiment_path, new_experimentID, configuration_parameters)

    # ==========================================================================
    # SERIAL COMMUNICATION SETUP & VIDEO ACQUISITION
    # ==========================================================================

    # Initialize serial communication with the second Raspberry Pi
    ser = serial_pi_comm.Serializer(configuration_parameters)

    # Start video acquisition (passing the full config dictionary)
    serial_pi_comm.send_byte_run_acquistions(ser, experiment_path, new_experimentID, configuration_parameters)

    # Close serial communication
    ser.close()

    # ==========================================================================
    # CLEANUP & FINAL LOGGING
    # ==========================================================================

    # Close log file
    logging.close_log_file(log_file)

    # Copy log file to the experiment folder for record-keeping
    shutil.copy(log_file.name, os.path.join(experiment_path, os.path.basename(log_file.name)))
