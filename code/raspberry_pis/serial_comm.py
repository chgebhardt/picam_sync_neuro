import serial
import camera, utils

class Serializer:
    """
    Serial communication utility for camera control.
    
    This class provides a serial communication utility for controlling cameras
    connected to a Raspberry Pi. It can initialize a serial port, open and close
    the port, send data to the connected device, and receive data from it.
    
    Parameters:
    camera_num (list): A list containing the camera number(s) to determine the port.
    baudrate (int): The baud rate for serial communication (default: 115200).
    timeout (int): The communication timeout in seconds (default: 1).
    
    Methods:
    - open(): Open the serial port for communication.
    - close(): Close the serial port.
    - send(serial_msg): Send data to the connected device via the serial port.
    - receive(): Receive data from the connected device via the serial port.
    
    Example:
    camera1 = Serializer(['1'])
    camera1.open()
    camera1.send(b"StartRecording")
    received_data = camera1.receive()
    camera1.close()
    """

    def __init__(self, camera_num, baudrate=115200, timeout=1):
        self.camera_num = camera_num
        self.port = self._initialize_serial_port(baudrate, timeout)
    
    def _initialize_serial_port(self, baudrate, timeout):
        port = None
        if self.camera_num == ['1']:
            port = serial.Serial(port='/dev/ttyUSB0', baudrate=baudrate, timeout=timeout,
                                writeTimeout=timeout, parity=serial.PARITY_NONE,
                                stopbits=serial.STOPBITS_ONE, bytesize=serial.EIGHTBITS)
        elif self.camera_num == ['2']:
            port = serial.Serial(port='/dev/ttyS0', baudrate=baudrate, timeout=timeout,
                                writeTimeout=timeout, parity=serial.PARITY_NONE,
                                stopbits=serial.STOPBITS_ONE, bytesize=serial.EIGHTBITS)
        return port

    def open(self):
        ''' Open the serial port.'''
        if not self.port.is_open:
            self.port.open()

    def close(self):
        ''' Close the serial port.'''
        if self.port.is_open:
            self.port.close()

    def send(self, serial_msg):
        if self.port.is_open:
            self.port.write(bytes(serial_msg))
        else:
            print("Serial port is not open. Cannot send data.")

    def receive(self):
        if self.port.is_open:
            return self.port.read()
        else:
            print("Serial port is not open. Cannot receive data.")  


def send_byte_run_acquistions(serial, configuration_parameters, FPS, RESOLUTION_PX, SHUTTERSPEED_US, CAMERA_MODE, BITRATE):
 
    """
    Send a signal byte and start video acquisitions for the specified camera.
    
    This function sends a signal byte over a serial connection and initiates video
    acquisitions for the specified camera. Depending on the camera number, it either
    waits for a signal from another device to start recording [pic1] or sends a signal to
    commence the recording process [pic2]. Timestamps are provided to indicate the start and
    end times of video acquisitions.
    
    Parameters:
    serial (SerialConnection): A serial connection for communication.
    camera_num (list): A list containing the camera number(s) to determine the action.
    
    Returns:
    None
    
    Example:
    send_byte_run_acquisitions(serial_connection, ['1'])
    send_byte_run_acquisitions(serial_connection, ['2'])
    """

    camera_num = configuration_parameters['camera_num']

    if camera_num == ['1']:
        serial_msg = bytearray()
        print_timestamp('\nWaiting for message from rpi2...')
        
        while not serial_msg:
            serial_msg = ser.receive()
        
        if serial_msg:
            utils.print_timestamp('\nRecording started at')
            
            camera.RecordVideo(experiment_path, new_experimentID, configuration_parameters, FPS, RESOLUTION_PX, SHUTTERSPEED_US, CAMERA_MODE, BITRATE)
            
            utils.print_timestamp('Recording finished at')
    
    elif camera_num == ['2']:
        serial.send(1)
        utils.print_timestamp('\nRecording started at')
        
        camera.RecordVideo(experiment_path, new_experimentID, configuration_parameters, FPS, RESOLUTION_PX, SHUTTERSPEED_US, CAMERA_MODE, BITRATE)
        
        utils.print_timestamp('Recording finished at')