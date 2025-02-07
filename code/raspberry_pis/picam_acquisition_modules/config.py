import yaml
import argparse

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

