# from picam_acquisition_modules import camera_acquisition, utils
# import serial

# class Serializer:
#     """
#     Serial communication utility for camera control.
    
#     This class provides a serial communication utility for controlling cameras
#     connected to a Raspberry Pi. It can initialize a serial port, open and close
#     the port, send data to the connected device, and receive data from it.
    
#     Parameters:
#     camera_num (list): A list containing the camera number(s) to determine the port.
#     baudrate (int): The baud rate for serial communication (default: 115200).
#     timeout (int): The communication timeout in seconds (default: 1).
    
#     Methods:
#     - open(): Open the serial port for communication.
#     - close(): Close the serial port.
#     - send(serial_msg): Send data to the connected device via the serial port.
#     - receive(): Receive data from the connected device via the serial port.
    
#     Example:
#     camera1 = Serializer(['1'])
#     camera1.open()
#     camera1.send(b"StartRecording")
#     received_data = camera1.receive()
#     camera1.close()
#     """
        
#     def __init__(self, configuration_parameters, baudrate=115200, timeout=1):
#         self.camera_num = configuration_parameters['camera_num']
#         self.port = self._initialize_serial_port(baudrate, timeout)
    
#     def _initialize_serial_port(self, baudrate, timeout):
#         port = None
#         if self.camera_num == ['1']:
#             port = serial.Serial(port='/dev/ttyUSB0', baudrate=baudrate, timeout=timeout,
#                                 writeTimeout=timeout, parity=serial.PARITY_NONE,
#                                 stopbits=serial.STOPBITS_ONE, bytesize=serial.EIGHTBITS)
#         elif self.camera_num == ['2']:
#             port = serial.Serial(port='/dev/ttyS0', baudrate=baudrate, timeout=timeout,
#                                 writeTimeout=timeout, parity=serial.PARITY_NONE,
#                                 stopbits=serial.STOPBITS_ONE, bytesize=serial.EIGHTBITS)
#         return port

#     def open(self):
#         ''' Open the serial port.'''
#         if not self.port.is_open:
#             self.port.open()

#     def close(self):
#         ''' Close the serial port.'''
#         if self.port.is_open:
#             self.port.close()

#     def send(self, serial_msg):
#         if self.port.is_open:
#             self.port.write(bytes(serial_msg))
#         else:
#             print("Serial port is not open. Cannot send data.")

#     def receive(self):
#         if self.port.is_open:
#             return self.port.read()
#         else:
#             print("Serial port is not open. Cannot receive data.")  


# def send_byte_run_acquistions(ser, experiment_path, new_experimentID, configuration_parameters):
 
#     """
#     Send a signal byte and start video acquisitions for the specified camera.
    
#     This function sends a signal byte over a serial connection and initiates video
#     acquisitions for the specified camera. Depending on the camera number, it either
#     waits for a signal from another device to start recording [pic1] or sends a signal to
#     commence the recording process [pic2]. Timestamps are provided to indicate the start and
#     end times of video acquisitions.
    
#     Parameters:
#     serial (SerialConnection): A serial connection for communication.
#     camera_num (list): A list containing the camera number(s) to determine the action.
    
#     Returns:
#     None
    
#     Example:
#     send_byte_run_acquisitions(serial_connection, ['1'])
#     send_byte_run_acquisitions(serial_connection, ['2'])
#     """
 
#     camera_num = configuration_parameters['camera_num']

#     if camera_num == ['1']:
#         serial_msg = bytearray()
#         utils.print_timestamp('\nWaiting for message from rpi2...')
        
#         while not serial_msg:
#             serial_msg = ser.receive()
        
#         if serial_msg:
#             utils.print_timestamp('\nRecording started at')
            
#             camera_acquisition.RecordVideo(experiment_path, new_experimentID, configuration_parameters)
            
#             utils.print_timestamp('Recording finished at')
    
#     elif camera_num == ['2']:
#         ser.send(1)
#         utils.print_timestamp('\nRecording started at')
        
#         camera_acquisition.RecordVideo(experiment_path, new_experimentID, configuration_parameters)
        
#         utils.print_timestamp('Recording finished at')

from picam_acquisition_modules import camera_acquisition, utils
import serial

class Serializer:
    """
    Serial communication utility for controlling cameras connected to a Raspberry Pi.

    This class provides the functionality to initialize a serial port, open and close
    the port, send data to the connected device, and receive data from it.

    Parameters:
    - camera_num (list): A list containing the camera number(s) used to determine the port.
    - baudrate (int): The baud rate for serial communication (default: 115200).
    - timeout (int): The communication timeout in seconds (default: 1).

    Methods:
    - open(): Opens the serial port for communication.
    - close(): Closes the serial port.
    - send(serial_msg): Sends data to the connected device via the serial port.
    - receive(): Receives data from the connected device via the serial port.

    Example usage:
    camera1 = Serializer(['1'])
    camera1.open()
    camera1.send(b"StartRecording")
    received_data = camera1.receive()
    camera1.close()
    """

    def __init__(self, configuration_parameters, baudrate=115200, timeout=1):
        """
        Initializes the Serializer class with configuration parameters.

        Args:
        - configuration_parameters (dict): The configuration dictionary containing camera number.
        - baudrate (int, optional): The baud rate for serial communication (default: 115200).
        - timeout (int, optional): The communication timeout in seconds (default: 1).
        """
        self.camera_num = configuration_parameters['camera_num']
        self.port = self._initialize_serial_port(baudrate, timeout)

    def _initialize_serial_port(self, baudrate, timeout):
        """
        Initializes the serial port based on the camera number.

        Args:
        - baudrate (int): The baud rate for serial communication.
        - timeout (int): The communication timeout in seconds.

        Returns:
        - serial.Serial: The initialized serial port.
        """
        if self.camera_num == ['1']:
            return serial.Serial(
                port='/dev/ttyUSB0', baudrate=baudrate, timeout=timeout,
                writeTimeout=timeout, parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE, bytesize=serial.EIGHTBITS
            )
        elif self.camera_num == ['2']:
            return serial.Serial(
                port='/dev/ttyS0', baudrate=baudrate, timeout=timeout,
                writeTimeout=timeout, parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE, bytesize=serial.EIGHTBITS
            )
        else:
            raise ValueError(f"Unsupported camera number: {self.camera_num}")

    def open(self):
        """Opens the serial port for communication."""
        if not self.port.is_open:
            self.port.open()

    def close(self):
        """Closes the serial port and restores standard output."""
        if self.port.is_open:
            self.port.close()

    def send(self, serial_msg):
        """Sends data to the connected device."""
        if self.port.is_open:
            self.port.write(bytes(serial_msg))
        else:
            print("Serial port is not open. Cannot send data.")

    def receive(self):
        """Receives data from the connected device."""
        if self.port.is_open:
            return self.port.read()
        else:
            print("Serial port is not open. Cannot receive data.")


def send_byte_run_acquisitions(ser, experiment_path, new_experimentID, configuration_parameters):
    """
    Sends a signal byte to control camera acquisition.

    This function sends a signal byte over a serial connection and initiates video
    acquisitions for the specified camera. Depending on the camera number, it either
    waits for a signal from another device to start recording (picamera 1), or sends
    a signal to commence the recording process (picamera 2). Timestamps are provided to
    indicate the start and end times of video acquisitions.

    Parameters:
    - ser (Serializer): The Serializer object used to communicate with the camera.
    - experiment_path (str): Path where the video will be stored.
    - new_experimentID (str): The unique experiment identifier.
    - configuration_parameters (dict): The configuration parameters for the experiment.

    Returns:
    - None

    Example usage:
    send_byte_run_acquisitions(serial_connection, '/path/to/experiment', 'experiment_01', configuration_parameters)
    """
    camera_num = configuration_parameters['camera_num']

    if camera_num == ['1']:
        serial_msg = bytearray()
        utils.print_timestamp('\nWaiting for message from rpi2...')

        # Wait for message from another Raspberry Pi (camera 2)
        while not serial_msg:
            serial_msg = ser.receive()
        
        if serial_msg:
            utils.print_timestamp('\nRecording started at')
            camera_acquisition.RecordVideo(experiment_path, new_experimentID, configuration_parameters)
            utils.print_timestamp('Recording finished at')

    elif camera_num == ['2']:
        # Camera 2 sends signal to start recording
        ser.send(1)
        utils.print_timestamp('\nRecording started at')

        camera_acquisition.RecordVideo(experiment_path, new_experimentID, configuration_parameters)
        utils.print_timestamp('Recording finished at')
