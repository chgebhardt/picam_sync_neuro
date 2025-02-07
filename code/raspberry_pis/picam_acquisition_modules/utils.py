import shutil
import sys
import datetime as dt

def disk_usage(path="/"):
    """
    Check available disk space and stop the script if space is critically low.
    """
    disk_info = shutil.disk_usage(path)
    free_GB = disk_info.free / 1e9
    print(f"\nThere are {free_GB:.2f} GB left on the disk at '{path}'")

    if free_GB < 10.0:
        print("There is less than 10GB of free space. Stopping the script.")
        sys.exit(1)  # Exit the script with a non-zero status code to indicate an error.

def print_timestamp(message):
    """
    Print a timestamp along with a custom message.
    """
    timestamp = dt.datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')
    print(f'{message} {timestamp}')
