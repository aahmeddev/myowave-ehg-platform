# MYOWAVE: Non-Invasive EHG Biosensor Platform

Developed as part of a Molecular Bioengineering design project at Imperial College London, **MYOWAVE** is a complete software ecosystem designed to acquire, process, and analyze uterine electromyography (EHG) signals. 

Built to support large-scale longitudinal menstrual health studies like the ENDO1000 project, this platform bridges the gap between raw hardware data acquisition and actionable clinical insights for conditions such as endometriosis, adenomyosis, and dysmenorrhea.

## Key Features

* **Real-Time DSP Engine**: A background service that interfaces with custom EHG hardware (Arduino/ADS1299) via serial communication. It applies high-pass Butterworth filtering, performs root-mean-square (RMS) event detection, and extracts spectral features like Fast Wave Low (FWL) and Fast Wave High (FWH) power using Welch's method.
* **Clinical Researcher Portal**: A secure, desktop-optimized dashboard built with NiceGUI. Researchers can monitor live hardware telemetry, track longitudinal patient trends, analyze morphological density profiles via Plotly clustering, and export standardized datasets.
* **Patient Portal**: A mobile-first web application enabling participants to authenticate securely, sync menstrual cycle days, log subjective pain scores, and view hardware connectivity status in real time.
* **Secure Cloud Synchronization**: Utilizes a nested NoSQL Firebase architecture for secure, pseudonymized data storage while maintaining a local SQLite database as a highly reliable fallback.
* **Automated Tunneling**: Integrated Cloudflare Quick Tunnels allow secure, immediate remote access to both portals during testing phases without complex network configuration.

## Technology Stack

* **Core Logic**: Python 3
* **User Interface**: NiceGUI, HTML/Tailwind CSS
* **Data Science & DSP**: Pandas, NumPy, SciPy, Plotly
* **Database**: Firebase (Firestore), SQLite3
* **Hardware Interface**: PySerial

## Repository Structure

* `launcher.py`: The master execution script that initializes the background DAQ service, launches both web portals, and configures Cloudflare tunnels.
* `background_service.py`: The continuous hardware polling and digital signal processing loop.
* `dsp_math.py`: Core mathematical functions for signal feature extraction.
* `dashboard.py` & `layout.py`: The entry point and shared UI wrapper for the researcher interface.
* `page_manager.py`, `page_cohort.py`, `page_patient.py`, `page_export.py`: Modular routing pages for clinical data analysis.
* `patient_app.py`: The standalone patient-facing web application.
* `config_db.py`: Database initialization and local/cloud synchronization protocols.
* `generate_synthetic_data.py`: A robust testing utility that generates clinically accurate, simulated EHG cohorts based on published physiological parameters.
* `Hardware_Testing/`: A suite of diagnostic scripts (`CapturePeriod.py`, `LiveCapture.py`, `T1_bandwidth_attenuation.py`, etc.) for validating the analogue front-end and CMRR performance.

## Getting Started

1. **Install Dependencies**: 
   Ensure you have Python installed, then install the required packages:
   ```bash
   pip install nicegui pandas numpy scipy plotly pyserial firebase-admin