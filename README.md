## picam_sync_neuro: Millisecond Precision Video Recording and Neurosignal Synchronization  

📝 Overview

This project enables millisecond precision synchronization of two Raspberry PiCamera video recordings from different angles and synchronizing them with each other and neural recordings. 

Achieving this requires:

A serial connection between two Raspberry Pis.  

A randomly blinking LED driven by an Arduino ISP for synchronization.  

A DAQ board to record LED voltage and neural signals.  

Custom post-processing code to synchronize the PiCameras with the DAQ signals.  

🚀 Features

✅ Dual PiCamera synchronization with millisecond precision  
✅ Arduino-driven LED synchronization  
✅ DAQ board integration for neural signal alignment  
✅ Optional manual start of the recording scripts on the Raspberry Pis or automation via ansible   
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

Clone the repository to both Pis and the main computer (eg. your laptop):

```
cd ~/Desktop/
git clone https://github.com/chgebhardt/picam_sync_neuro.git
```
install dependencies on your main computer:   
```
cd picam_sync_neuro 
conda env create -f python_dependencies_reqs.yml
conda activate picam_sync_neuro
```

2️⃣ Hardware Setup

- Connect Raspberry Pis via a serial-to-USB link. For that I followed this 
[link](https://practicingelectronics.wordpress.com/2018/04/22/serial-port-for-a-raspberry-pi-using-a-usb-to-serial-adapter/).

- Set up the Arduino as ISP and connect the LED.

- Configure DAQ board inputs for LED voltage recording.  
This depends very much on what kind of system you have. Most DAQs will have a BNC input so I soldered a female pre-assembeled BNC into the arduino circuit on the breadboard. Then it is just a matter of telling your DAQ which Input to listen to.
  

3️⃣ Run the main.py script on both Pis:

- VNC into both Pis and open a terminal in each one
- then modify the config.yaml according your needs (has to be the same on both Pis):
  ```
  cd ~/Desktop/picam_sync_neuro/code/raspberry_pis
  nano config.yaml
  ```
- first, run this on rpi1 (serial msg receiver) and then on the rpi2 (serial msg sender):
  ```
  python3 main.py config.yaml 
  ```
(optional: Install a scheduler on your main computer e.g. ansible)
```
sudo apt get update
sudo apt get install ansible
```
(optional: Setup an inventory.ini file containing the IP addresses of your Pis)
```
nano inventory.ini
```
(optional: Modify the config.yaml on the main computer)
```
nano config.yaml
```
(optional: Start the ansible-playbook on the main computer. This takes care of the transfer of the same config.yaml and also the timing of both Pis.)
```
ansible-playbook -i inventory.ini run_pi_behavior_script.yaml --ask-become-pass -e "source_directory=/home/<username>/Desktop/picam_sync_neuro/code/raspberry_pis"
```


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
