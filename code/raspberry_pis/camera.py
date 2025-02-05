import picamera
import io
import datetime as dt
import time

class TimeStamp(object):
    """
    Class for issuing timestamps and saving them to CSV files.

    This class is designed for capturing timestamps from a picamera, specifically
    the PTS (from GPU) and pi STC, and saving them into CSV files. It can be
    used for video timestamp synchronization.

    Parameters:
    camera (Camera): The camera object providing frame data and timestamps.
    video_filename (str): The filename for the video output file.
    timestamp_filename (str): The filename for the CSV file to save timestamps.

    Methods:
    - write(buf): Write frame data and capture timestamps from the camera.
    - flush(): Save the captured timestamps to a CSV file.
    - close(): Close the video output file.

    Example:
    camera = Camera()
    timestamp = TimeStamp(camera, "video_output.mp4", "timestamps.csv")
    timestamp.write(frame_data)
    timestamp.flush()
    timestamp.close()
    """
    
    def __init__(self, camera, video_filename, timestamp_filename):
        self.camera         = camera
        self._video_output  = io.open(video_filename, 'wb')
        self._timestampFile = timestamp_filename
        self._timestamps    = []
        
    def write(self, buf):
        if self.camera.frame.complete is not None:
            if self.camera.frame.timestamp is None: # the first I-Frame and all SPS-Headers do not possess timestamps and are thus flagged with a timestamp of -1000 
               timestamp = -1000 
            else:
               timestamp = self.camera.frame.timestamp
            
            self._timestamps.append(
                ( self.camera.frame.index, self.camera.frame.frame_type, timestamp, time.time() )
                )
        
        return self._video_output.write(buf)
    
    def flush(self):
        with io.open(self._timestampFile, 'w') as f:
            f.write('index, frame_type, GPU Time, time.time()\n')
            for entry in self._timestamps:
                f.write('%d,%d,%d,%f\n' % entry)
        
    def close(self):
        self._video.close()




def RecordVideo(experiment_path, new_experimentID, configuration_parameters, FPS, RESOLUTION_PX, SHUTTERSPEED_US, CAMERA_MODE, BITRATE):

    with picamera.PiCamera() as camera: 
      
        camera.resolution  = RESOLUTION_PX
        camera.framerate   = FPS
        camera.sensor_mode = CAMERA_MODE
        
        # preview while recording?
        if configuration_parameters['camera_preview']:
           camera.start_preview(fullscreen = False, window = (400, 70, 640, 320))  
        
        # timestamp settings
        camera.annotate_background = picamera.Color('black')
        camera.annotate_text       = dt.datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')
        
        videoTime = time.strftime('%H%M%S')
        
        # create file names for videos
        videoName  = new_experimentID + '_' + videoTime + ".h264"
        path_video = os.path.join(experiment_path, videoName)
        
        if 'IR' in configuration_parameters['illumination']:  
            
            camera.iso           = 300
            camera.shutter_speed = SHUTTERSPEED_US # in microseconds
            camera.awb_mode      = 'off'
            
            if camera_num == ['1']:
               rg , bg           = (0.8, 0.9) # automatic awb_mode is not working in NOIR picamera with firmware pre 07/2019!!!
            
            elif camera_num == ['2']:
               rg , bg           = (0.9, 0.85)
            
            camera.awb_gains     = (rg,bg) 
            camera.brightness    = 60               # [def 50,    0 100]
            camera.contrast      = 80               # [def  0, -100 100]
            
    
        elif 'RL' in configuration_parameters['illumination']:
            camera.awb_mode = 'auto'
        
        output = TimeStamp(camera, path_video, os.path.join(experiment_path, new_experimentID + '_clock.csv'))
    
        camera.start_recording(output, format = 'h264', bitrate = BITRATE)  
        
        start = dt.datetime.now()
        while (dt.datetime.now() - start).seconds < configuration_parameters['video_duration_mins'] * 60:
            camera.annotate_text = dt.datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')                                     
            camera.annotate_text_size = 15
    
        camera.stop_recording()
        
        if camera_preview:
            camera.stop_preview()