import re
import os.path
import cv2
import subprocess
import getpass
from pathlib import Path
import glob
import numpy as np
import csv
from datetime import datetime


def get_exp_foldernames(homedir, date):
    '''
    
    '''
    dir_content = os.listdir(homedir)

    exp_folders = [string for string in dir_content if date in string]
    exp_folders.sort()

    exp_dict = dict.fromkeys(exp_folders)
    
    for key, value in {**exp_dict}.items():
        exp_dict[key] = "".join([homedir, key])
        
    return exp_dict


def convert_h264_to_mp4(exp_dict, fps = 40):
    '''
    convert raw h264 into "reliably seekable" mp4 if the mp4 files do not exist yet
    https://sleap.ai/help.html?highlight=ffmpeg
    '''
    
    for exp, exp_folder in {**exp_dict}.items():
        
        Path(exp_folder + '/01_picams/02_conv/').mkdir(parents=True, exist_ok=True)        
        
        for input_file in glob.glob(exp_folder + '/01_picams/01_raw/*.h264'):
            
            split_string = Path(input_file).stem.rsplit('_', 1)
            output_fname = split_string[0]
            
            output_file = exp_folder + '/01_picams/02_conv/' + output_fname
            
            if not os.path.exists(output_file + '.mp4'):
            
                # original transcoding as in bash script
                # subprocess.call(['ffmpeg', '-vsync', '0' , '-r', str(fps), '-i', input_file, '-codec', 'copy', output_file + '.mp4'])
                
                # creates reliably seekable mp4 from h264
                subprocess.call(['ffmpeg', '-vsync', '0',
                                 '-r', str(fps), 
                                 '-i', input_file, 
                                 '-c:v', 'libx264',
                                 '-pix_fmt', 'yuv420p',
                                 '-preset', 'superfast',
                                 '-crf', '19',
                                 output_file + '.mp4'])
                
            else:
                
                print('[{0}] ({1}) {2} already exists!\n'.format(datetime.now().strftime("%H:%M:%S"), convert_h264_to_mp4.__name__, exp_folder + '/01_picams/02_conv/' + output_fname + '.mp4'))
                
    return  0


def select_rectangle_coordinates(video_path, num_frames=50):
    '''
    Allows the user to select a rectangle on an average frame generated from the first `num_frames` of the video.
    (press 'r' to redo drawing the rectangl or press 'q' to save the rectangle)
    
    Parameters:
        input_video (cv2.VideoCapture): Video capture object.
        num_frames (int, optional): Number of frames to use for generating the average frame. Default is 50.
    
    Returns:
        Tuple (x1, x2, y1, y2): Coordinates of the selected rectangle (top-left and bottom-right corners).
    '''
    
    print(video_path)
    input_video  = cv2.VideoCapture(video_path)
    
    frame_count = 0
    sum_frame   = None

    while frame_count < num_frames:
        ret, frame = input_video.read()
        if not ret:
            break
        
        frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        if sum_frame is None:
            sum_frame = np.zeros_like(frame, dtype=np.float32)
        
        sum_frame += frame
        frame_count += 1
        
    average_frame = sum_frame / frame_count
    frame_copy    = np.uint8(average_frame)

    cv2.namedWindow('Select Rectangle')
    cv2.imshow('Select Rectangle', frame_copy)

    x1, y1, x2, y2 = 0, 0, 0, 0
    drawing = False

    def draw_rectangle(event, x, y, flags, param):
        nonlocal drawing, x1, y1, x2, y2

        if event == cv2.EVENT_LBUTTONDOWN:
            drawing = True
            x1, y1 = x, y
        elif event == cv2.EVENT_LBUTTONUP:
            drawing = False
            x2, y2 = x, y
            cv2.rectangle(frame_copy, (x1, y1), (x2, y2), (255, 255, 255), 1)
            cv2.imshow('Select Rectangle', frame_copy)

    cv2.setMouseCallback('Select Rectangle', draw_rectangle)

    while True:
        cv2.imshow('Select Rectangle', frame_copy)
        key = cv2.waitKey(1) & 0xFF

        if key == ord('r'): # press 'r' to redo drawing the rectangle
            frame_copy = np.uint8(average_frame)
            drawing = False
        elif key == ord('q') or key == 27: # press 'q' to save the rectangle
            break

    cv2.destroyAllWindows()
    input_video.release() 

    return x1, x2, y1, y2


def generate_LED_values_csv(homedir, exp_dict):
    '''
    this function takes an experiment number as input (essentially a mp4 movie) and calculates 
    the average intensity values from a rectangle around the expected position of the infrared 
    blinking LED (the position is not determined automatically atm)  
    '''
    
    for exp, exp_folder in {**exp_dict}.items():
    
        picam_list = find_picams(exp_folder)
        
        LED_values = list()
            
        for picam_id in picam_list:

            fname  = exp_folder + '/01_picams/01_raw/' + exp + '_' + picam_id + '_LEDvalues.csv'

            if not os.path.exists(fname):

                folder     = exp_folder + '/01_picams/02_conv/'
                video_path = folder + exp + '_' + picam_id + '.mp4'
                
                x1, x2, y1, y2 = select_rectangle_coordinates(video_path)

                input_video  = cv2.VideoCapture(video_path)
                
                frame_num = 0
                success   = True

                while success:

                    success, frame = input_video.read()
                    
                    if success == True:  

                        ######################################################################################################
                        # apply operation on frames here

                        frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

                        # LED value index starts at 1 as does FIJI!!!
                        if picam_id == 'pic1':

                            # x1, x2 = 1188, 1230
                            # y1, y2 =  325,  368

                            LED_values.append((frame_num+1, np.mean(frame[y1:y2, x1:x2])))
                            frame = cv2.rectangle(frame, (x1,y1), (x2,y2), [255,255,255], 1)

                        elif picam_id == 'pic2':

                            # x1, x2 = 1244, 1280
                            # y1, y2 =  260,  304

                            LED_values.append((frame_num+1, np.mean(frame[y1:y2, x1:x2])))
                            frame = cv2.rectangle(frame, (x1,y1), (x2,y2), [255,255,255], 1)

                        ######################################################################################################

                        cv2.imshow('frame', frame)

                        if cv2.waitKey(1) & 0xFF == ord('q'):
                            break

                    else:
                        break

                    frame_num +=1

                file = open(homedir + exp + '/01_picams/01_raw/'  + exp + '_' + picam_id + '_LEDvalues.csv', 'w+', newline ='')

                # writing the list into a file
                with file:    
                    write = csv.writer(file)
                    write.writerow(['Slice', 'Mean'])
                    write.writerows(LED_values)

                # release the video capture and video write objects 
                input_video.release() 

                # close all windows 
                cv2.destroyAllWindows() 

                LED_values = list()  

            else:
                print('[{0}] ({1}) File {2} already exists!\n'.format(datetime.now().strftime("%H:%M:%S"), generate_LED_values_csv.__name__, exp + '_' + picam_id + '_LEDvalues.csv'))
                
    return 0


def find_picams(exp_path):
    """
    Finds unique picam modifiers (pic1, pic2, ...) in the specified folder.

    Parameters:
    - folder_path (str): Path to the folder containing the files.

    Returns:
    - picam_list (list): List of unique picam identifiers.
    """
    
    # exp contains the folder path to the experiment including homedir
    folder_path = exp_path + '/01_picams/01_raw/'
    picam_set   = set()

    # Iterate through all files in the folder
    for filename in os.listdir(folder_path):
        # Use regular expression to match pic followed by digits
        match = re.search(r'pic(\d+)', filename)
        if match:
            picam_set.add('pic' + match.group(1))

    # Convert the set to a sorted list
    picam_list = sorted(list(picam_set))

    if not picam_list:
        print("No picamera found!")
    
    return picam_list
