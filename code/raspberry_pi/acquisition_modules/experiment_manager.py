import datetime as dt
from pathlib import Path
import sys
from picam_acquisition_modules import config

def create_experiment_folder(configuration_parameters):
    """
    Create a new experiment folder for data storage.

    This function generates a unique experiment folder path based on the current date,
    experiment number, and camera number. It ensures the folder does not already exist
    before creating it.

    Parameters:
    - configuration_parameters (dict): Dictionary containing configuration parameters 
      (e.g., experimenter name, experiment number, camera number).

    Returns:
    - tuple: A tuple containing the experiment folder path and the experiment identifier.

    Raises:
    - SystemExit: If the folder already exists, the script exits with an error message.

    Example:
    exp_path, new_expID = create_experiment_folder(configuration_parameters)
    """
    experimenter = configuration_parameters['experimenter']
    exp_num      = configuration_parameters['exp_num']
    camera_num   = configuration_parameters['camera_num']
    
    # Define root path where experiment data will be stored
    root_path = Path('/home/pi/Desktop/Behavior') / experimenter

    # Generate the experiment folder name based on the current date
    currentDate = dt.datetime.now().strftime("%Y%m%d")
    new_expID = f"{currentDate}_e{exp_num}_pic{camera_num[0]}"
    exp_path = root_path / new_expID

    print(f'\nCreating new experiment folder for {new_expID}...')
    
    if exp_path.exists():
        print(f"Experiment folder '{new_expID}' already exists. Exiting the script.")
        sys.exit()  # Exits the script if the folder already exists
    else:
        exp_path.mkdir(parents=True, exist_ok=True)
        print('Folder created!')

    return exp_path, new_expID


def write_metadata(exp_path, new_experimentID, configuration_parameters):
    """
    Create a metadata text file for the experiment.

    This function writes metadata related to the experiment, such as the experimenter, 
    animal information, camera settings, and other relevant parameters to a text file. 
    The text file is saved in the experiment folder.

    Parameters:
    - exp_path (Path): The path where the metadata text file will be saved.
    - new_experimentID (str): The unique identifier for the experiment.
    - configuration_parameters (dict): A dictionary containing experiment settings.

    Returns:
    - None

    Raises:
    - Exception: If there is an issue writing the metadata file, an exception is raised.

    Example:
    write_metadata(exp_path, new_experimentID, configuration_parameters)
    """
    metadata = {
        'experimenter': configuration_parameters['experimenter'],
        'exp_num': configuration_parameters['exp_num'],
        'camera_num': configuration_parameters['camera_num'][0],
        'view': configuration_parameters['view'],
        'illumination': configuration_parameters['illumination'],
        'video_duration_mins': configuration_parameters['video_duration_mins'],
        'fps': configuration_parameters['FPS'],
        'resolution_px': configuration_parameters['RESOLUTION_PX'],
        'shutterspeed_us': configuration_parameters['SHUTTERSPEED_US'],
        'bitrate': configuration_parameters['BITRATE']
    }

    # Build the metadata file name and content
    meta_fname      = f"{new_experimentID}.txt"
    metadata_lines  = [f"{new_experimentID}"]  # Include experiment ID as the first line
    metadata_lines += [f"{key}:{value}" for key, value in metadata.items()]

    metadata_text   = "\n".join(metadata_lines)

    try:
        # Write metadata to the file
        with open(exp_path / meta_fname, "w") as file:
            file.write(metadata_text)
        print('\nMetadata file created successfully!')
    except Exception as e:
        # If there's an error, print it
        print(f'\nError saving metadata file: {str(e)}')
