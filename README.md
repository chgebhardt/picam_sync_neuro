## picam_sync_neuro: Millisecond Precision Video Recording and Neurosignal Synchronization  

📝 Overview

This project enables millisecond synchronization of two Raspberry PiCamera video recordings from different angles and synchronizing them with each other and neural recordings. 

Achieving this requires:

A serial connection between two Raspberry Pis.  

A randomly blinking LED driven by an Arduino ISP for synchronization.  

A DAQ board to record LED voltage and neural signals.  

Custom post-processing code to synchronize the PiCameras with the DAQ signals.  

🚀 Features

✅ Dual PiCamera synchronization with millisecond precision  
✅ Arduino-driven LED synchronization  
✅ DAQ board integration for neural signal alignment  
✅ Robust post-processing pipeline  

🛠️ Hardware & Components

Required Hardware

2× Raspberry Pi 3B+ v1.3 (32-bit Raspbian) with NO-IR PiCamera modules

1× Serial-to-USB cable to connect the Raspberry Pis

1× Arduino as an ISP for LED control

1× DAQ Board (e.g., Fiber Photometry or Open-Ephys rig) for voltage and neural signal recording

910nm Infrared LED + Resistors + Wires


📂 Installation & Setup

1️⃣ Software Installation

Clone the repository and install dependencies:

git clone https://github.com/yourusername/picam_sync_neuro.git  
cd picam_sync_neuro 
conda env create -f python_dependencies_reqs.yml
conda activate picam_sync_neuro

2️⃣ Hardware Setup

Connect Raspberry Pis via a serial-to-USB link. I followed:  
https://practicingelectronics.wordpress.com/2018/04/22/serial-port-for-a-raspberry-pi-using-a-usb-to-serial-adapter/

Set up the Arduino ISP and connect the LED.

Configure DAQ board inputs for LED voltage recording.  
###This depends very much on what kind of system you have. Most DAQs will have a BNC input so I soldered a female pre-assembeled BNC to the arduino breadboard. Then it is just a matter of telling your DAQ which Input to listen to.   

3️⃣ Running the Synchronization Code

python software/raspberry_pi/sync_record.py --config config.yaml  

📊 Data Processing & Synchronization

Timestamps from PiCameras & DAQ board are aligned using post_process.py.

LED signals are extracted and used for fine-tuning timestamps.

Final synchronized video outputs can be analyzed in analysis/.

📜 License

- **Code** is licensed under the [MIT License](LICENSE).
- **Documentation, images, and non-code materials** are licensed under [Creative Commons Attribution 4.0 (CC-BY 4.0)](LICENSE-docs).

🤝 Contributing

Pull requests and feature suggestions are welcome! See CONTRIBUTING.md for guidelines.

🔗 References & Acknowledgments

This project was inspired by various open-source tutorials and resources. See ACKNOWLEDGMENTS.md for full credits.
