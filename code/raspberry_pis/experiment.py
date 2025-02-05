import datetime as dt
from pathlib import Path
import sys

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


# def write_metadata(exp_path, config):
#     """
#     Create a metadata text file for experiment information.

#     This function generates a text file containing metadata related to an
#     experiment, and it dynamically reads the content from the provided config dictionary.
#     The text file is named after the experiment's unique identifier and is stored in the specified experiment path.

#     Parameters:
#     exp_path (str): The path where the metadata text file will be saved.
#     config (dict): The dictionary containing metadata parameters.

#     Returns:
#     None
#     """
#     meta_fname      = f"{config['experiment_id']}.txt"
#     metadata_lines  = [f"{config['experiment_id']}"]  # Include the expID identifier
#     metadata_lines += [f"{key}:{value}" for key, value in config.items() if key != 'experiment_id']

#     metadata_text = "\n".join(metadata_lines)

#     try:
#         with open(exp_path / meta_fname, "w") as file:
#             file.write(metadata_text)
#         print('\nTxt-file for Metadata created!')
#     except Exception as e:
#         print(f'\nCould not save txt-file for Metadata: {str(e)}')
