import picamera
import io
import os
import datetime as dt
import time

class TimeStamp:
    """
    Handles timestamping for PiCamera video recordings.

    This class captures timestamps from the PiCamera, including:
    - PTS (Presentation Timestamp) from the GPU
    - Pi system timestamps from time.time()

    It writes timestamps to a CSV file alongside the recorded video.

    Parameters:
    - camera (PiCamera): The active PiCamera object.
    - video_filename (str): Path to save the video file.
    - timestamp_filename (str): Path to save the timestamp file.

    Methods:
    - write(buf): Captures frame timestamps and writes video data.
    - flush(): Saves the captured timestamps to the CSV file.
    - close(): Closes the video file.

    Example:
        camera = picamera.PiCamera()
        timestamp_writer = TimeStamp(camera, "video.h264", "timestamps.csv")
        camera.start_recording(timestamp_writer, format="h264")
        camera.stop_recording()
        timestamp_writer.close()
    """

    def __init__(self, camera, video_filename, timestamp_filename):
        self.camera = camera
        self._video_output = io.open(video_filename, 'wb')
        self._timestampFile = timestamp_filename
        self._timestamps = []

    def write(self, buf):
        """Write video frame data and capture timestamp information."""
        if self.camera.frame.complete is not None:
            if self.camera.frame.timestamp is None:
                # The first I-Frame and all SPS-Headers do not possess timestamps and are thus flagged with a timestamp of -1000
                timestamp = -1000  
            else:
                timestamp = self.camera.frame.timestamp
            
            self._timestamps.append(
                (self.camera.frame.index, self.camera.frame.frame_type, timestamp, time.time())
            )

        return self._video_output.write(buf)

    def flush(self):
        """Save the captured timestamps to a CSV file."""
        with io.open(self._timestampFile, 'w') as f:
            f.write('index, frame_type, GPU Time, time.time()\n')
            for entry in self._timestamps:
                f.write(f"{entry[0]},{entry[1]},{entry[2]},{entry[3]:.6f}\n")

    def close(self):
        """Close the video output file."""
        self._video_output.close()


def RecordVideo(experiment_path, new_experimentID, configuration_parameters):
    """
    Records video using the Raspberry Pi Camera with timestamping.

    This function:
    - Initializes the PiCamera with settings from `configuration_parameters`
    - Configures exposure, white balance, and resolution
    - Records a timestamped video to the experiment folder

    Parameters:
    - experiment_path (str): The directory to save recordings.
    - new_experimentID (str): Unique experiment identifier.
    - configuration_parameters (dict): Configuration parameters from `config.yaml`.

    Returns:
    - None
    """

    # Extract camera settings from configuration
    FPS                 = configuration_parameters['FPS']
    RESOLUTION_PX       = configuration_parameters['RESOLUTION_PX']
    SHUTTERSPEED_US     = configuration_parameters['SHUTTERSPEED_US']
    CAMERA_MODE         = configuration_parameters['CAMERA_MODE']
    BITRATE             = configuration_parameters['BITRATE']
    camera_num          = configuration_parameters['camera_num']
    illumination        = configuration_parameters['illumination']
    camera_preview      = configuration_parameters['camera_preview']
    video_duration_mins = configuration_parameters['video_duration_mins']

    with picamera.PiCamera() as camera:
        # Apply camera settings
        camera.resolution  = RESOLUTION_PX
        camera.framerate   = FPS
        camera.sensor_mode = CAMERA_MODE

        # Preview while recording?
        if camera_preview:
            camera.start_preview(fullscreen=False, window=(400, 70, 640, 320))  

        # Timestamp overlay settings
        camera.annotate_background = picamera.Color('black')
        camera.annotate_text       = dt.datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')

        # Generate a unique filename based on experiment ID and current time
        video_time = time.strftime('%H%M%S')
        video_name = f"{new_experimentID}_{video_time}.h264"
        path_video = os.path.join(experiment_path, video_name)

        # Adjust camera settings based on illumination conditions
        if 'IR' in illumination:  
            # IR mode settings for NO-IR PiCamera
            camera.iso           = 300
            camera.shutter_speed = SHUTTERSPEED_US  # in microseconds
            camera.awb_mode      = 'off'  # Disable automatic white balance

            # Set white balance gains manually (required for pre-07/2019 firmware)
            if camera_num == ['1']:
                rg, bg = (0.8, 0.9)
            elif camera_num == ['2']:
                rg, bg = (0.9, 0.85)

            camera.awb_gains  = (rg, bg) 
            camera.brightness = 60  # Default: 50, Range: 0-100
            camera.contrast   = 80  # Default: 0, Range: -100 to 100

        elif 'RL' in illumination:
            # RL (Regular Light) mode uses auto white balance
            camera.awb_mode = 'auto'

        # Initialize timestamp writer for saving timestamps to CSV
        timestamp_filename = os.path.join(experiment_path, f"{new_experimentID}_clock.csv")
        output             = TimeStamp(camera, path_video, timestamp_filename)

        # Start video recording with timestamps
        camera.start_recording(output, format='h264', bitrate=BITRATE)

        # Recording loop (runs for the specified duration)
        start_time = dt.datetime.now()
        while (dt.datetime.now() - start_time).seconds < video_duration_mins * 60:
            camera.annotate_text      = dt.datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')                                     
            camera.annotate_text_size = 15  # Ensure timestamp text is readable

        # Stop recording and preview
        camera.stop_recording()
        if camera_preview:
            camera.stop_preview()
