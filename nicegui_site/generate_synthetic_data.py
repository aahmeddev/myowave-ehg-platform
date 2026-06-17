"""
generate_synthetic_data.py
Generates complete synthetic EHG data for testing and validation.
Execute this script to wipe existing Signal Testing data and instantiate a fresh 100-patient cohort.
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import random
import os
from config_db import init_firebase

# Configuration Parameters
NUM_PATIENTS = 100
SESSIONS_PER_PATIENT = 50
EVENTS_PER_SESSION = (3, 8)  # Minimum and maximum events per session.
DIAGNOSES = ["Healthy", "Endometriosis", "Dysmenorrhea", "Adenomyosis"]
DIAGNOSIS_WEIGHTS = [0.4, 0.25, 0.2, 0.15]  # Diagnostic distribution weights.

# CSV export column order. Includes cycle_day for Firebase event synchronization.
EXPORT_COLUMNS = [
    "diagnosis", "patient_id", "session_id", "event_id",
    "timestamp_start", "rms_v", "max_amplitude_v", "burst_duration_sec",
    "ibi_sec", "dominant_freq_hz", "power_fwh", "power_fwl", "pain_scale", "cycle_day"
]

db_cloud = init_firebase()

def generate_patient_id(diagnosis: str, index: int) -> str:
    """Generate a patient ID with the appropriate diagnosis prefix."""
    prefix_map = {
        "Healthy": "HE",
        "Endometriosis": "EN",
        "Dysmenorrhea": "DY",
        "Adenomyosis": "AD"
    }
    prefix = prefix_map.get(diagnosis, "UN")
    return f"{prefix}{index:04d}"

def generate_session_id(patient_id: str, session_num: int) -> str:
    """Generate a chronologically unique session ID."""
    timestamp = datetime.now().strftime("%Y%m%d")
    return f"{patient_id}_S{session_num:02d}_{timestamp}"

def generate_event_id(session_id: str, event_num: int) -> str:
    """Generate a sequential event ID."""
    return f"{session_id}_EV{event_num:03d}"

def generate_realistic_ehg_params(diagnosis: str) -> dict:
    """
    Generate accurate EHG parameters based on diagnosis.
    Calculations mirror published physiological research ranges for specific conditions.
    """
    if diagnosis == "Healthy":
        rms_mean, rms_std = 0.05, 0.02
        amp_mean, amp_std = 0.08, 0.03
        dur_mean, dur_std = 30, 10
        ibi_mean, ibi_std = 120, 30
        freq_mean, freq_std = 0.4, 0.1
        fwh_mean, fwh_std = 0.3, 0.1
        fwl_mean, fwl_std = 0.2, 0.08
        pain = random.randint(0, 2)

    elif diagnosis == "Endometriosis":
        rms_mean, rms_std = 0.12, 0.04
        amp_mean, amp_std = 0.18, 0.05
        dur_mean, dur_std = 45, 15
        ibi_mean, ibi_std = 90, 25
        freq_mean, freq_std = 0.8, 0.2
        fwh_mean, fwh_std = 0.6, 0.15
        fwl_mean, fwl_std = 0.5, 0.12
        pain = random.randint(7, 10)

    elif diagnosis == "Dysmenorrhea":
        rms_mean, rms_std = 0.08, 0.03
        amp_mean, amp_std = 0.12, 0.04
        dur_mean, dur_std = 35, 12
        ibi_mean, ibi_std = 100, 28
        freq_mean, freq_std = 0.6, 0.15
        fwh_mean, fwh_std = 0.45, 0.12
        fwl_mean, fwl_std = 0.35, 0.1
        pain = random.randint(5, 8)

    elif diagnosis == "Adenomyosis":
        rms_mean, rms_std = 0.15, 0.05
        amp_mean, amp_std = 0.22, 0.06
        dur_mean, dur_std = 50, 18
        ibi_mean, ibi_std = 75, 20
        freq_mean, freq_std = 1.0, 0.25
        fwh_mean, fwh_std = 0.75, 0.18
        fwl_mean, fwl_std = 0.65, 0.15
        pain = random.randint(6, 9)

    else:
        rms_mean, rms_std = 0.08, 0.03
        amp_mean, amp_std = 0.12, 0.04
        dur_mean, dur_std = 35, 12
        ibi_mean, ibi_std = 100, 30
        freq_mean, freq_std = 0.6, 0.15
        fwh_mean, fwh_std = 0.45, 0.12
        fwl_mean, fwl_std = 0.35, 0.1
        pain = random.randint(0, 10)

    return {
        "rms_v": max(0.01, np.random.normal(rms_mean, rms_std)),
        "max_amplitude_v": max(0.02, np.random.normal(amp_mean, amp_std)),
        "burst_duration_sec": max(5, int(np.random.normal(dur_mean, dur_std))),
        "ibi_sec": max(10, np.random.normal(ibi_mean, ibi_std)),
        "dominant_freq_hz": max(0.1, np.random.normal(freq_mean, freq_std)),
        "power_fwh": max(0.05, np.random.normal(fwh_mean, fwh_std)),
        "power_fwl": max(0.02, np.random.normal(fwl_mean, fwl_std)),
        "pain_scale": pain
    }

def generate_timestamp_base() -> datetime:
    """Generate a realistic randomized timestamp for a session within the last 30 days."""
    days_ago = random.randint(0, 30)
    hours_offset = random.randint(0, 23)
    minutes_offset = random.randint(0, 59)
    return datetime.now() - timedelta(days=days_ago, hours=hours_offset, minutes=minutes_offset)

def wipe_firebase_database():
    """Recursively delete all patient documents and their subcollections from the Firebase database."""
    print("\nInitiating complete database wipe...")
    patients_ref = db_cloud.collection('patients').stream()

    deleted_count = 0
    for pt in patients_ref:
        # Delete sessions subcollection.
        sessions_ref = pt.reference.collection('sessions').stream()
        for session in sessions_ref:
            # Delete event documents.
            for event in session.reference.collection('events').stream():
                event.reference.delete()
            # Delete pain log documents.
            for pain in session.reference.collection('pain_logs').stream():
                pain.reference.delete()
            # Delete the session document.
            session.reference.delete()

        # Delete the root patient document.
        pt.reference.delete()
        deleted_count += 1

    print(f"✓ Erased {deleted_count} patients and all associated nested data.")

def generate_synthetic_data():
    """Generate synthetic cohort data utilizing realistic physiological constraints."""
    print("Generating synthetic EHG cohort data...")
    all_events = []

    today = datetime.now().date()

    for diag_idx, diagnosis in enumerate(DIAGNOSES):
        num_diag_patients = int(NUM_PATIENTS * DIAGNOSIS_WEIGHTS[diag_idx])
        if diag_idx == len(DIAGNOSES) - 1:
            num_diag_patients = NUM_PATIENTS - sum(
                int(NUM_PATIENTS * DIAGNOSIS_WEIGHTS[i]) for i in range(len(DIAGNOSES) - 1)
            )

        for pat_idx in range(1, num_diag_patients + 1):
            patient_id = generate_patient_id(diagnosis, pat_idx)

            # Chronological Timeline Calculations
            # Establish an anchor date representing Cycle Day 1.
            patient_anchor_date = today - timedelta(days=random.randint(0, 27))

            # Calculate the current cycle day based on the anchor date.
            current_cycle_day = ((today - patient_anchor_date).days % 28) + 1

            for session_num in range(1, SESSIONS_PER_PATIENT + 1):
                session_start = generate_timestamp_base()
                num_events = random.randint(*EVENTS_PER_SESSION)

                # Determine the exact cycle day for the specific session date.
                days_since_anchor = (session_start.date() - patient_anchor_date).days
                session_cycle_day = (days_since_anchor % 28) + 1

                session_id = generate_session_id(patient_id, session_num)

                for event_num in range(1, num_events + 1):
                    event_id = generate_event_id(session_id, event_num)
                    event_offset = timedelta(seconds=random.randint(0, 1800))
                    event_timestamp = session_start + event_offset

                    params = generate_realistic_ehg_params(diagnosis)

                    event = {
                        "diagnosis": diagnosis,
                        "patient_id": patient_id,
                        "current_cycle_day": current_cycle_day, # For the patient root document.
                        "cycle_day": session_cycle_day,         # For the specific event/session.
                        "session_id": session_id,
                        "event_id": event_id,
                        "timestamp_start": event_timestamp.timestamp(),
                        **params
                    }
                    all_events.append(event)

    df = pd.DataFrame(all_events)

    # Format dataframe for CSV export.
    export_df = df.copy()
    numeric_cols = ["rms_v", "max_amplitude_v", "ibi_sec", "dominant_freq_hz", "power_fwh", "power_fwl"]
    for col in numeric_cols:
        export_df[col] = export_df[col].round(4)
    export_df["burst_duration_sec"] = export_df["burst_duration_sec"].round(1)
    export_df["timestamp_start"] = export_df["timestamp_start"].round(1)

    # Export dataframe to a local CSV file.
    output_path = os.path.join(os.path.dirname(__file__), "synthetic_cohort_data.csv")
    export_df[EXPORT_COLUMNS].to_csv(output_path, index=False)

    print(f"✓ Generated {len(df)} events for {NUM_PATIENTS} patients")
    print(f"✓ Saved local copy to: {output_path}")

    return df

def upload_to_firebase(df):
    """Upload data adopting the appropriate nested NoSQL architecture."""
    print("\nUploading data to nested Firebase architecture...")
    batch = db_cloud.batch()
    op_count = 0

    # Group data by patient to establish root documents.
    patients = df.groupby('patient_id')

    for pt_id, pt_group in patients:
        diag = pt_group['diagnosis'].iloc[0]
        current_cycle_day = int(pt_group['current_cycle_day'].iloc[0])

        # 1. Initialize the root patient document.
        pt_ref = db_cloud.collection('patients').document(pt_id)
        batch.set(pt_ref, {
            "diagnosis": diag,
            "pin": "1234",
            "current_cycle_day": current_cycle_day
        })
        op_count += 1

        # Group patient data by individual sessions.
        sessions = pt_group.groupby('session_id')
        for sess_id, sess_group in sessions:
            start_ts = float(sess_group['timestamp_start'].min())

            # 2. Initialize the session document.
            sess_ref = pt_ref.collection('sessions').document(sess_id)
            batch.set(sess_ref, {
                "started_at": start_ts,
                "diagnosis": diag,
                "connection_status": "active"
            })
            op_count += 1

            # 3. Append a unified pain log for the session.
            pain = int(sess_group['pain_scale'].iloc[0])
            pain_ref = sess_ref.collection('pain_logs').document(str(int(start_ts)))
            batch.set(pain_ref, {
                "timestamp": start_ts,
                "pain_scale": pain
            })
            op_count += 1

            # 4. Upload all event data into the corresponding session subcollection.
            for _, event_row in sess_group.iterrows():
                ev_id = event_row['event_id']
                ev_data = event_row[EXPORT_COLUMNS].to_dict()

                ev_ref = sess_ref.collection('events').document(ev_id)
                batch.set(ev_ref, ev_data)
                op_count += 1

                # Commit the batch operation if the Firebase limit is reached.
                if op_count >= 400:
                    batch.commit()
                    print("  Committed data batch...")
                    batch = db_cloud.batch()
                    op_count = 0

    # Commit any remaining batch operations.
    if op_count > 0:
        batch.commit()

    print("✓ Successfully built nested database structure in Firebase!")


if __name__ == "__main__":
    response = input("WARNING: This will permanently erase all data in your Firebase database. Continue? (y/n): ").strip().lower()
    if response == 'y':
        wipe_firebase_database()
        df_synthetic = generate_synthetic_data()
        upload_to_firebase(df_synthetic)
        print("\nAll tasks complete. Your system is ready for testing.")
    else:
        print("Operation cancelled.")