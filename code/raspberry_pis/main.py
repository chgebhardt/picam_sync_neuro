import shutil
import os
from code import config, logging, experiment, camera, serial_comm, utils


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
    
    # Load configuration parameters from config.yaml
    config_data = config.parse_and_load_config()

    # Set up logging
    log_file = create_log_file('/home/pi/Desktop/logs/pic{}_log.out'.format(camera_num[0]))

    # Check disk usage
    experiment.disk_usage()

    # Create experiment folder and save metadata
    exp_path, exp_id = experiment.create_experiment_folder(config_data['experimenter'], config_data['exp_num'], config_data['camera_num'])
    shutil.copy(__file__, str(exp_path) + os.sep + os.path.basename(__file__))
    experiment.write_metadata(exp_path, config_data)

    # Set up serial communication
    ser = serial_comm.Serializer(config_data['camera_num'])
    serial_comm.send_byte_run_acquisitions(ser, config_data['camera_num'], config_data['FPS'], config_data['RESOLUTION_PX'], config_data['SHUTTERSPEED_US'], config_data['CAMERA_MODE'], config_data['BITRATE'])

    # Close serial port and log file
    ser.close()
    logging.close_log_file(log_file)

    # Copy the log file to the experiment folder
    shutil.copy(log_file.name, str(exp_path) + os.sep + os.path.basename(log_file.name))
