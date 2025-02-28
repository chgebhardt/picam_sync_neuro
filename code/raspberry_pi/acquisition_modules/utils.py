import shutil
import sys
import datetime as dt

def disk_usage(path="/"):
    """
    Check available disk space and stop the script if space is critically low.

    This function checks the available disk space at the specified path. If the free
    space is below a critical threshold (default: 10GB), it prints a warning and stops
    the script with a non-zero exit code.

    Parameters:
    - path (str, optional): The path to check disk space for. Defaults to the root path.

    Returns:
    - None

    Raises:
    - SystemExit: If the free disk space falls below the critical threshold, the script exits.
    """
    try:
        # Get disk usage info
        disk_info = shutil.disk_usage(path)
        free_GB = disk_info.free / 1e9  # Convert from bytes to gigabytes
        print(f"\nThere are {free_GB:.2f} GB left on the disk at '{path}'")

        # Check if disk space is below the critical threshold (10GB)
        if free_GB < 10.0:
            print("Warning: Less than 10GB of free space available. Stopping the script.")
            sys.exit(1)  # Exit the script with a non-zero status code to indicate an error.
    except Exception as e:
        print(f"Error checking disk usage: {e}")
        sys.exit(1)  # Exit if there is an issue retrieving disk space info

def print_timestamp(message):
    """
    Print a timestamp along with a custom message.

    This function prepends the current timestamp to a given message and prints it to
    the console. The timestamp is formatted as 'YYYY-MM-DD HH:MM:SS.mmmmmm'.

    Parameters:
    - message (str): The custom message to be printed alongside the timestamp.

    Returns:
    - None
    """
    timestamp = dt.datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')
    print(f'{message} {timestamp}')
