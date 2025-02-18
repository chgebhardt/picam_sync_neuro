import picamera
from time import sleep

with picamera.PiCamera() as camera:

    # resolution and framerate has to be chosen first before playing with exposure and awb
    # otherwise it will overwrite awb and exposure gains
    camera.sensor_mode = 6
    camera.framerate   = 40
    camera.resolution  = (1280,720)
    camera.iso = 300
    camera.shutter_speed = 3000 #in microseconds
    #camera.exposure_mode = 'off'
   
    #Wait for the automatic gain control to settle
    #sleep(2)
    # Now fix the values
    camera.awb_mode = 'off'
    
    rg , bg = (0.80, 0.90)
    camera.awb_gains = (rg, bg)
    camera.brightness = 60
    camera.contrast   = 80

    #camera.start_preview(fullscreen=False, window = (200, 50, 1160, 590))
    camera.start_preview(fullscreen=False, window = (400, 70, 640, 320))
   
    
    sleep(60*30)
    camera.stop_preview()



    
