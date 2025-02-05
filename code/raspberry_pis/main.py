import shutil
import os
import sys
import re, socket
import config, logging, experiment, serial_comm, utils


if __name__ == '__main__':
   
    # get hostname / camera_number / script name (important because different parts of the script are run on different pis) 
    host        = socket.gethostname()     # extract hostname
    camera_num  = re.findall(r'\d+', host) # extract list of numberstr from string
    script_path = sys.argv[0]
    script_name = os.path.basename(script_path)

    # load config yaml file
    configuration_parameters = config.parse_and_load_config()
    
    # access the metadata parameters
    experimenter             = configuration_parameters['experimenter']                
    exp_num                  = configuration_parameters['exp_num']
    beh_paradigm_id          = configuration_parameters['beh_paradigm_id']

    # Define mappings for camera_num and beh_paradigm_id
    camera_num_mapping       = {'1': 'front', '2': 'top'}
    beh_paradigm_mapping     = {'pr': 'pup_retrieval', 'rm': 'retrieval_motivation'}

    # Use the mappings to transform the respective metadata values
    configuration_parameters['camera_num']        = camera_num
    configuration_parameters['script_name']       = script_name
    configuration_parameters['view']              = camera_num_mapping.get(camera_num[0], camera_num[0])
    configuration_parameters['behavior_paradigm'] = beh_paradigm_mapping.get(beh_paradigm_id, beh_paradigm_id)
    
    #==========================================================================
    # Acquisition parameters
    #==========================================================================

    # set hard-coded recording parameters 
    # (easier hardcoding because some of the parameter combinations are hard-coded in the picams) 
    
    FPS                = 40          
    RESOLUTION_PX      = (1280,720)
    SHUTTERSPEED_US    = 3000            # shutter speed in microseconds
    CAMERA_MODE        = 6
    BITRATE            = 7000000          # video encoding bitrate (has an influence on dropped picam frames)

    # save hardcoded acquisition parameters to configuration_parameters
    configuration_parameters['FPS']             = FPS
    configuration_parameters['RESOLUTION_PX']   = RESOLUTION_PX
    configuration_parameters['SHUTTERSPEED_US'] = SHUTTERSPEED_US
    configuration_parameters['BITRATE']         = BITRATE

    # Create a log file (using the default "log.out" if no path is provided)
    log_file = logging.create_log_file('/home/pi/Desktop/logs/pic{}_log.out'.format(camera_num[0]))

    # Check available Diskspace
    utils.disk_usage()

    # Create new experiment folder and save metadata file
    experiment_path, new_experimentID = experiment.create_experiment_folder(experimenter, exp_num, camera_num)
    
    # copy python script to experiment folder
    shutil.copy(__file__, str(experiment_path) + os.sep + os.path.basename(__file__)) 
    
    # Writes metadata file to the experiment_path
    experiment.write_metadata(experiment_path, new_experimentID, configuration_parameters)
    
    # serial port initialization (uses camera_num as list), send byte from rpi2 to rpi1 and acquistion start
    ser = serial_comm.Serializer(camera_num)
    
    serial_comm.send_byte_run_acquistions(ser, configuration_parameters, FPS, RESOLUTION_PX, SHUTTERSPEED_US, CAMERA_MODE, BITRATE)
    
    ser.close()

    # Close the log file
    logging.close_log_file(log_file)
