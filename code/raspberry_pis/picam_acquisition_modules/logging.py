import sys

def create_log_file(log_file_path=None):
    """
    Create a log file for writing and redirect standard output to the file.
    If log_file_path is not provided, use the default "log.out".
    """
    if log_file_path is None:
        log_file_path = "log.out"

    log_file   = open(log_file_path, "w")
    sys.stdout = log_file
    return log_file


def close_log_file(log_file):
    """
    Close the log file and restore standard output to the console.
    """
    sys.stdout = sys.__stdout__
    log_file.close()