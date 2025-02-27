import sys

def create_log_file(log_file_path=None):
    """
    Create a log file and redirect standard output to it.

    If no path is provided, the default is "log.out". The function also redirects
    the standard output (sys.stdout) to this file, so all print statements
    will be written to the log file.

    Parameters:
    - log_file_path (str, optional): Path where the log file will be saved. Defaults to "log.out".
    
    Returns:
    - log_file (file object): The opened log file object for further writing.

    Raises:
    - IOError: If there is an issue opening the log file (e.g., file permission issues).
    """
    if log_file_path is None:
        log_file_path = "log.out"

    try:
        log_file = open(log_file_path, "w")
        sys.stdout = log_file
        return log_file
        
    except IOError as e:
        print(f"Error opening log file: {e}")
        sys.exit(1)  # Exit if the log file cannot be opened


def close_log_file(log_file):
    """
    Close the log file and restore the standard output to the console.

    This function ensures that the log file is properly closed and that
    print statements will be directed back to the console (stdout) after logging is done.

    Parameters:
    - log_file (file object): The log file object that needs to be closed.
    
    Returns:
    - None
    """
    try:
        sys.stdout = sys.__stdout__  # Restore stdout to console
        log_file.close()  # Close the log file
    except Exception as e:
        print(f"Error closing log file: {e}")
