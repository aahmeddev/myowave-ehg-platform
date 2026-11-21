import json
import os
import sqlite3

import firebase_admin
from firebase_admin import credentials, firestore

DB_NAME = "ehg_research.db"
FIREBASE_KEY_PATH = os.environ.get("FIREBASE_KEY_PATH", "firebase_key.json")


def setup_local_db() -> None:
    """Initialise local SQLite tables for raw EHG recordings, processed events, and patients."""
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS raw_contractions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT,
                patient_id TEXT,
                timestamp REAL,
                voltage REAL,
                event_id INTEGER
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS processed_events (
                event_id INTEGER PRIMARY KEY,
                session_id TEXT
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS patients (
                patient_id TEXT PRIMARY KEY,
                diagnosis TEXT,
                pin TEXT
            )
            """
        )
        conn.commit()


def init_firebase():
    """Initialise the Firebase Admin SDK once and return a Firestore client."""
    if not firebase_admin._apps:
        cred = credentials.Certificate(FIREBASE_KEY_PATH)
        firebase_admin.initialize_app(cred)
    return firestore.client()


def read_session_control() -> dict:
    """Read the shared session control state, defaulting to stopped if absent or invalid."""
    if not os.path.exists("session_control.json"):
        return {"is_running": False}
    try:
        with open("session_control.json", "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return {"is_running": False}
