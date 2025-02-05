## picam_sync_neuro: Millisecond Precision Video Recording and Neurosignal Synchronization  

📝 Overview

This project enables millisecond synchronization of (currently) two Raspberry Pi Cameras recordings from different angles and synchronizing that with neuro recordings. 
Achieving this precision required:

A serial connection between two Raspberry Pis.

A blinking LED driven by an Arduino ISP for synchronization.

A DAQ board to record LED voltage for post-processing alignment with neurosignal.

Custom post-processing code to synchronize the PiCameras with the DAQ signal.

🚀 Features

✅ Dual PiCamera synchronization within millisecond precision
✅ Arduino-driven LED synchronization system
✅ DAQ board integration for external signal alignment
✅ Robust post-processing pipeline for data correction

🛠️ Hardware & Components

Required Hardware

2× Raspberry Pi 3B+ (32-bit Raspbian) with NO-IR PiCamera modules

1× Serial-to-USB cable to connect the Raspberry Pis

1× Arduino (Model X) as an ISP for LED control

1× DAQ Board (e.g., Fiber Photometry, Open-Ephys) for voltage and neuro signal recording

910nm Infrared LED + Resistors + Wires

Optional: External trigger input for additional hardware integration

📂 Installation & Setup

1️⃣ Software Installation

Clone the repository and install dependencies:

git clone https://github.com/yourusername/picam_sync_neuro.git  
cd picam_sync_neuro 
conda env create -f python_dependencies_reqs.yml

2️⃣ Hardware Setup

Connect Raspberry Pis via a serial-to-USB link.

Set up the Arduino ISP and connect the LED.

Configure DAQ board inputs for LED voltage recording.

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
