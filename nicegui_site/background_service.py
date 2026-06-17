import sys
import serial
import numpy as np
import sqlite3
import time
import threading
import pandas as pd
import os
import json
from collections import deque
from scipy.signal import butter, lfilter, lfilter_zi
from config_db import setup_local_db, init_firebase, read_session_control, DB_NAME
from dsp_math import extract_features

# Configuration Parameters
PORT = 'COM3'
BAUD = 115200
FS = 250
TIME_STEP = 1.0 / FS  # Exactly 0.004 seconds per sample.
HPF_CUTOFF = 0.3
EVENT_THRESHOLD_RMS = 0.04

setup_local_db()
db_cloud = init_firebase()


# Real-Time Digital Signal Processing (DSP) Synchronization Thread
def process_and_upload_worker():
    conn = sqlite3.connect(DB_NAME, check_same_thread=False)
    previous_end_time = None
    ibi_history = []

    while True:
        ctrl = read_session_control()
        if not ctrl.get("is_running", False):
            time.sleep(2)
            continue

        session_id = ctrl["session_id"]
        patient_id = ctrl["patient_id"]

        # Identify unprocessed raw physiological events in the local database.
        query = f"""
            SELECT DISTINCT event_id FROM raw_contractions 
            WHERE session_id = '{session_id}' 
            AND event_id NOT IN (SELECT event_id FROM processed_events)
        """
        unprocessed = pd.read_sql_query(query, conn)['event_id'].tolist()

        for eid in unprocessed:
            df_event = pd.read_sql_query(f"SELECT * FROM raw_contractions WHERE event_id = {eid}", conn)
            features = extract_features(df_event, previous_end_time, ibi_history)

            if features:
                # Append required clinical metadata.
                features.update({"patient_id": patient_id, "session_id": session_id})
                features.update(ctrl.get("metadata", {}))

                # 1. Persist computed features to local CSV storage.
                df_feat = pd.DataFrame([features])
                hdr = not os.path.exists('session_history.csv')
                df_feat.to_csv('session_history.csv', mode='a', header=hdr, index=False)

                # 2. Synchronize computed features with Firebase cloud infrastructure.
                doc_ref = db_cloud.collection('patients').document(patient_id) \
                    .collection('sessions').document(session_id) \
                    .collection('events').document(str(eid))
                doc_ref.set(features)
                print(f"Cloud Sync: Event {eid} uploaded for {patient_id}.")

                previous_end_time = df_event['timestamp'].iloc[-1]

            # Update local database registry to mark the event as fully processed.
            conn.execute("INSERT INTO processed_events (event_id, session_id) VALUES (?, ?)", (eid, session_id))
            conn.commit()

        time.sleep(2)


threading.Thread(target=process_and_upload_worker, daemon=True).start()

# Hardware Data Acquisition (DAQ) Loop
try:
    ser = serial.Serial(PORT, BAUD, timeout=0.1)
    print("Background Service Active. Waiting for Streamlit to start a session...")
except Exception as e:
    print(f"Hardware Error: {e}")
    sys.exit()

b, a = butter(2, HPF_CUTOFF, btype='highpass', fs=FS)
filter_state = None
rms_buffer = deque([0.0] * FS, maxlen=FS)
pre_buffer = deque(maxlen=FS * 2)

is_recording = False
current_chunk = []
current_event_id = 0
post_event_counter = 0

# Initialize timing variables for high-precision sample tracking.
last_sample_timestamp = time.time()

conn_daq = sqlite3.connect(DB_NAME, check_same_thread=False)
c_daq = conn_daq.cursor()

while True:
    ctrl = read_session_control()
    if not ctrl.get("is_running", False):
        if 'ser' in locals() and ser.is_open:
            ser.reset_input_buffer()
        filter_state = None
        time.sleep(0.5)
        continue

    session_id = ctrl["session_id"]
    patient_id = ctrl["patient_id"]

    try:
        while ser.in_waiting > 0:
            line_raw = ser.readline().decode('utf-8', errors='ignore').strip()
            if line_raw:
                try:
                    val = float(line_raw)

                    actual_now = time.time()
                    if actual_now - last_sample_timestamp > 0.5:
                        sample_time = actual_now
                    else:
                        sample_time = last_sample_timestamp + TIME_STEP

                    last_sample_timestamp = sample_time

                    if filter_state is None:
                        filter_state = lfilter_zi(b, a) * val

                    filtered_array, filter_state = lfilter(b, a, [val], zi=filter_state)
                    rms_buffer.append(filtered_array[0])
                    current_rms = np.sqrt(np.mean(np.square(list(rms_buffer))))

                    if not is_recording:
                        pre_buffer.append((session_id, patient_id, sample_time, val))
                        if current_rms >= EVENT_THRESHOLD_RMS:
                            is_recording = True
                            current_event_id = int(sample_time)
                            print(f"\n[EVENT TRIGGERED] Contraction detected! RMS: {current_rms:.4f}.")

                            for pt in pre_buffer:
                                current_chunk.append((pt[0], pt[1], pt[2], pt[3], current_event_id))
                            pre_buffer.clear()
                    else:
                        current_chunk.append((session_id, patient_id, sample_time, val, current_event_id))
                        if current_rms < EVENT_THRESHOLD_RMS:
                            post_event_counter += 1
                            if post_event_counter >= (FS * 2):
                                is_recording = False
                                post_event_counter = 0
                                print(f"[EVENT ENDED] Contraction closed. Finalizing database write block.")

                                if len(current_chunk) > 0:
                                    c_daq.executemany(
                                        "INSERT INTO raw_contractions (session_id, patient_id, timestamp, voltage, event_id) VALUES (?, ?, ?, ?, ?)",
                                        current_chunk)
                                    conn_daq.commit()
                                    current_chunk.clear()
                        else:
                            post_event_counter = 0

                    if len(current_chunk) >= 50:
                        c_daq.executemany(
                            "INSERT INTO raw_contractions (session_id, patient_id, timestamp, voltage, event_id) VALUES (?, ?, ?, ?, ?)",
                            current_chunk)
                        conn_daq.commit()
                        current_chunk.clear()
                except ValueError:
                    continue


    except serial.SerialException:
        print("\n[CRITICAL ERROR] Hardware connection lost! Attempting auto-recovery...", flush=True)
        # 1. Transmit hardware disconnection alert to cloud infrastructure.
        db_cloud.collection('patients').document(patient_id).collection('sessions').document(session_id).update({
            "connection_status": "disconnected"
        })
        # 2. Terminate serial connection to safely release operating system COM resources.
        if 'ser' in locals():
            try:
                ser.close()
            except:
                pass
        # 3. Initiate automated recovery sequence without terminating the active session control.
        reconnected = False
        while not reconnected:
            # Maintain web portal interactivity to allow manual session termination during extended hardware outages.
            if not read_session_control().get("is_running", False):
                break
            try:
                ser = serial.Serial(PORT, BAUD, timeout=0.1)
                reconnected = True
                print("\n[RECOVERY SUCCESSFUL] Hardware reconnected. Resuming data stream...", flush=True)
                # Restore the active connection status in Firebase.
                db_cloud.collection('patients').document(patient_id).collection('sessions').document(session_id).update(
                    {
                        "connection_status": "active"
                    })
                # Purge buffers and reset DSP filter states to prevent algorithmic divergence upon reconnection.
                ser.reset_input_buffer()
                filter_state = None
                last_sample_timestamp = time.time()
            except serial.SerialException:
                time.sleep(2)  # Implement a 2-second backoff delay prior to subsequent hardware polling.