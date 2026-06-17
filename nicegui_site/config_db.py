import sqlite3
import firebase_admin
from firebase_admin import credentials, firestore
import json
import os

DB_NAME = "ehg_research.db"


def setup_local_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()

    # Create table for raw voltage recordings.
    c.execute('''CREATE TABLE IF NOT EXISTS raw_contractions
                 (
                     id
                     INTEGER
                     PRIMARY
                     KEY
                     AUTOINCREMENT,
                     session_id
                     TEXT,
                     patient_id
                     TEXT,
                     timestamp
                     REAL,
                     voltage
                     REAL,
                     event_id
                     INTEGER
                 )''')

    # Create table to track events that have been processed and uploaded.
    c.execute('''CREATE TABLE IF NOT EXISTS processed_events
                 (
                     event_id
                     INTEGER
                     PRIMARY
                     KEY,
                     session_id
                     TEXT
                 )''')

    c.execute('''CREATE TABLE IF NOT EXISTS patients
                 (
                     patient_id
                     TEXT
                     PRIMARY
                     KEY,
                     diagnosis
                     TEXT,
                     pin
                     TEXT
                 )''')

    conn.commit()
    conn.close()


def init_firebase():
    if not firebase_admin._apps:
        cred = credentials.Certificate("firebase_key.json")
        firebase_admin.initialize_app(cred)
    return firestore.client()


def read_session_control():
    if not os.path.exists("session_control.json"):
        return {"is_running": False}
    try:
        with open("session_control.json", "r") as f:
            return json.load(f)
    except:
        return {"is_running": False}