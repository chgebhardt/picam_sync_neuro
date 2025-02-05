import shutil
import os
import sys
import re, socket
from code import config, logging, experiment, serial_comm, utils


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
    # (easier hardcoding because some of the parameter combinations are hard-coded in the picams) 
    
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
    log_file = logging.create_log_file('/home/pi/Desktop/logs/pic{}_log.out'.format(camera_num[0]))

    # Check available Diskspace
    utils.disk_usage()

    # Create new experiment folder and save metadata file
    experiment_path, new_experimentID = experiment.create_experiment_folder(experimenter, exp_num, camera_num)
    
    # copy python script to experiment folder
    shutil.copy(__file__, str(experiment_path) + os.sep + os.path.basename(__file__)) 
    
    # Write metadata file to the experiment_path
    experiment.write_metadata(experiment_path)
    
    # serial port initialization (uses camera_num as list), send byte from rpi2 to rpi1 and acquistion start
    ser = serial_comm.Serializer(camera_num)
    
    serial_comm.send_byte_run_acquistions(ser, camera_num, FPS, RESOLUTION_PX, SHUTTERSPEED_US, CAMERA_MODE, BITRATE)
    
    ser.close()

    # Close the log file
    close_log_file(log_file)
