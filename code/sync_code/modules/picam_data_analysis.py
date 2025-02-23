# Standard Library Imports
from datetime import datetime
import inspect
import os
import re

# Third-Party Libraries
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt


def analyze_picam_times(homedir, expID, picam_dict, verbose=False):
    """
    Analyze picamera timestamps for each camera ('pic1' and 'pic2') in the picam_dict.
    If the analysis has already been performed, skip re-analysis.
    """
    function_name = inspect.currentframe().f_code.co_name

    results = {}
    picam_list = find_picams(homedir, expID)
    
    # Check if analysis has already been performed
    if picam_dict.get('picam_frame_analysis_run', True):
        print(f"\n[{datetime.now():%H:%M:%S}] ({function_name}) PICAM Frame Analysis already completed for Experiment {picam_dict['expID']}. Skipping re-analysis.")

        print(f'\n[{datetime.now():%H:%M:%S}] ({function_name}) PICAM Frame Analysis SUMMARY:')
        
        for picam_id in picam_list:
            
            total_frames = len(picam_dict[picam_id]['picam_timing']['picam_frame_info'].index)
            dropped_frames_df = picam_dict[picam_id]['picam_timing']['dropped_frames_df']
            total_dropped = int(np.sum(dropped_frames_df['num_dropped_frames'].to_numpy()))
            
            print(f"\n   Frame analysis for {picam_id}:")
            print(f"      Total number of picam frames found: {total_frames}")
            print(f"      Total number of dropped picam frames: {total_dropped}")
        
        return picam_dict

    print(f"\n\n[{datetime.now():%H:%M:%S}] ({function_name}) Analyzing picam frame times for experiment {picam_dict['expID']}:")

    for picam_id in picam_list:
        # Extract picam_frame_info and picam_metadata for each camera from picam_dict
        frame_df = picam_dict[picam_id]['picam_timing']['picam_frame_info']
        fps      = picam_dict[picam_id]['picam_metadata']['fps']

        # Identify dropped frames and create a dropped frames DataFrame
        dropped_frames_indices, dropped_frames_count = identify_dropped_frames(frame_df, fps)
        dropped_frames_df = create_dropped_frames_dataframe(frame_df, dropped_frames_indices, dropped_frames_count)

        total_frames = len(frame_df.index)
        total_dropped = int(np.sum(dropped_frames_count.to_numpy()))

        print(f"\nFrame analysis for {picam_id}:")
        print(f"   Total number of picam frames found: {total_frames}")
        print(f"   Total number of dropped picam frames: {total_dropped}")

        if verbose:
            plot_frame_intervals(frame_df, dropped_frames_df, picam_id)

        # Ensure 'picam_timing' exists, or create it if it doesn’t
        if 'picam_timing' not in picam_dict[picam_id]:
            picam_dict[picam_id]['picam_timing'] = {}

        # Update only the frame_df and dropped_frames_df keys without overwriting the rest
        picam_dict[picam_id]['picam_timing'].update({
            'dropped_frames_df': dropped_frames_df
        })

    # Set a flag indicating that picam frame analysis was run
    picam_dict['picam_frame_analysis_run'] = True
    print(f"\n[{datetime.now():%H:%M:%S}] ({function_name}) Analysis of picam frame timing completed for experiment {picam_dict['expID']}.")

    return picam_dict


def find_picams(homedir, expID):
    '''
    Finds unique picam modifiers (pic1, pic2, ...) in the working folder.
    Only processes .txt files.
    '''
    
    folder = os.path.join(homedir, expID, '01_picams', '01_raw')

    # Get unique picam identifiers from .txt files containing 'pic'
    picam_identifiers = {re.split('[_.]', f)[2] for f in os.listdir(folder) 
                         if f.endswith('.txt') and 'pic' in f and len(re.split('[_.]', f)) > 2}

    picam_list = sorted(picam_identifiers)  # Sort the unique identifiers

    if not picam_list:
        print("No picamera found!")
        return []
    
    return picam_list
    

def identify_dropped_frames(frame_df, fps):
    """
    Identify dropped frames based on interframe intervals.
    """
    dropped_frame_condition = frame_df['frame_interval_GPU_time_sec'] >= (1.3 / float(fps))
    dropped_frames_indices = frame_df[dropped_frame_condition].index
    dropped_frames_count = np.round(frame_df.loc[dropped_frame_condition, 'frame_interval_GPU_time_sec'] /
                                            frame_df['frame_interval_GPU_time_sec'].median(), 0) - 1
   
    return dropped_frames_indices, dropped_frames_count


def create_dropped_frames_dataframe(frame_df, dropped_frames_indices, dropped_frames_count):
    """
    Create a DataFrame containing information about dropped frames.
    """
    segment_numbers = np.ceil(dropped_frames_indices / 2000 - 1)
    
    dropped_frames_data = np.array((dropped_frames_indices.to_numpy(),
                                     frame_df['GPU_time_sec'][dropped_frames_indices].to_numpy(),
                                     frame_df['frame_interval_GPU_time_sec'][dropped_frames_indices].to_numpy(),
                                     dropped_frames_count.astype('int').to_numpy(),
                                     segment_numbers)).T

    dropped_frames_df = pd.DataFrame(dropped_frames_data[:, 1:], 
                                      index=dropped_frames_data[:, 0].astype(int), 
                                      columns=['GPU_time_sec', 'frame_interval_GPU_time_sec', 'num_dropped_frames', 'mp4_segment'])
   
    return dropped_frames_df.astype({'num_dropped_frames': int, 'mp4_segment': int})


def plot_frame_intervals(frame_df, dropped_frames_df, picam_id):
    """
    Plot the interframe intervals and annotate dropped frames.
    """
    plt.figure(figsize=(10, 3), constrained_layout=True)
    
    # Plotting the interframe intervals
    plt.plot(frame_df.index, frame_df['frame_interval_GPU_time_sec'], 'k-', linewidth=0.5, label=picam_id)
    plt.xlabel('Picam Frame Number', fontsize=12)
    plt.ylabel('Interframe Interval [sec]', fontsize=12)
    plt.title('Picamera Interframe Interval Analysis', fontsize=13)
    plt.legend(fontsize=10, loc='upper right')

    # Calculate median for setting ylim
    median_interval = frame_df['frame_interval_GPU_time_sec'].median()
    plt.ylim(0.995 * median_interval, 1.005 * median_interval)  # Set ylim based on median

    # Get the current ylim
    ymin, ymax = plt.ylim()

    # Draw and annotate the median line
    plt.axhline(y=median_interval, color='red', linestyle='--', linewidth=1)
    # Prepare median text as a formatted string
    median_text = f'median: {median_interval:.4f}s\ncalculated fps: {1/median_interval:.2f}'
    # Add the median textbox in the upper right corner
    plt.gca().text(0.13, 0.95, median_text, transform=plt.gca().transAxes,
                   fontsize=8, verticalalignment='top', 
                   horizontalalignment='right', 
                   bbox=dict(boxstyle='round,pad=0.5', edgecolor='red', facecolor='white'))
    # Add an arrow from the textbox to the median line
    plt.annotate('', 
             xy=(-4000, median_interval),  # Position on the median line (x, y) in data coordinates
             xytext=(0.05, 0.84),   # Position of the textbox (x, y) in axes coordinates
             textcoords='axes fraction', # Ensure the textbox coordinates are interpreted as axes fraction
             arrowprops=dict(arrowstyle='->', color='red', lw=1))


    # Annotate dropped frames
    dropped_text = "\n".join([f"({int(index)}, {int(row['num_dropped_frames'])})" 
                               for index, row in dropped_frames_df.iterrows()])
    
    
    # Add the textbox in the lower right corner
    plt.gca().text(0.98, 0.05, dropped_text, transform=plt.gca().transAxes,
                   fontsize=8, verticalalignment='bottom', 
                   horizontalalignment='right', 
                   bbox=dict(boxstyle='round,pad=0.5', edgecolor='red', facecolor='white'))


    # Annotate peaks and draw red vertical lines for dropped frames
    for index, row in dropped_frames_df.iterrows():

        # Draw a red vertical line at GPU_time_sec
        plt.axvline(x=int(index), color='red', linestyle='-', linewidth=2)

    plt.grid(True)
    plt.show()
