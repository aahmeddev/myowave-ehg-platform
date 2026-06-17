from nicegui import ui
import json
import time
import os
import pandas as pd
import plotly.express as px
from datetime import datetime
from page_cohort import clear_cohort_vault
from config_db import init_firebase, read_session_control, DB_NAME
from layout import frame

db_cloud = init_firebase()


def load_grouped_patients():
    """Retrieve all patient IDs grouped by diagnosis for hierarchical interface selection."""
    grouped = {"Healthy": [], "Endometriosis": [], "Adenomyosis": [], "Dysmenorrhea": []}
    docs = db_cloud.collection('patients').stream()
    for doc in docs:
        data = doc.to_dict()
        diag = data.get('diagnosis', 'Healthy')
        if diag in grouped:
            grouped[diag].append(doc.id)
        else:
            # Handle unexpected diagnostic categories gracefully.
            grouped[diag] = [doc.id]
    return grouped


@ui.refreshable
def render_telemetry_console(session_id, patient_id):
    """Render a live telemetry status bar for hardware, patient pain, and the most recent event."""

    # 1. Retrieve current hardware connection status.
    session_doc = db_cloud.collection('patients').document(patient_id).collection('sessions').document(session_id).get()
    hw_status = "Unknown"
    if session_doc.exists:
        hw_status = session_doc.to_dict().get("connection_status", "active")

    # 2. Retrieve the most recent patient pain log.
    pain_logs = db_cloud.collection('patients').document(patient_id).collection('sessions').document(
        session_id).collection('pain_logs').get()
    latest_pain = "None reported"
    if pain_logs:
        sorted_logs = sorted([doc.to_dict() for doc in pain_logs], key=lambda x: x.get('timestamp', 0))
        if sorted_logs:
            latest_pain = f"{sorted_logs[-1].get('pain_scale')} / 10"

    # 3. Retrieve recent event metrics and calculate static latency.
    latest_event_str = "Awaiting event..."
    if os.path.exists('session_history.csv'):
        try:
            df = pd.read_csv('session_history.csv')
            df_session = df[df['session_id'] == session_id]

            if not df_session.empty:
                last_row = df_session.iloc[-1]

                # Check both timestamp_start and event_id to prevent KeyErrors.
                event_time_raw = last_row.get('timestamp_start', last_row.get('event_id'))

                if pd.notna(event_time_raw):
                    event_time = float(event_time_raw)

                    # Calculate static latency based on file modification timestamps.
                    file_mtime = os.path.getmtime('session_history.csv')
                    latency_sec = file_mtime - event_time

                    timestamp_str = datetime.fromtimestamp(event_time).strftime('%H:%M:%S')

                    # Format metrics securely for the user interface.
                    latest_event_str = f"[{timestamp_str}] RMS: {last_row.get('rms_v', 0):.4f}V | Freq: {last_row.get('dominant_freq_hz', 0):.2f}Hz | Dur: {last_row.get('burst_duration_sec', 0):.1f}s | Latency: {latency_sec:.1f}s"
                else:
                    latest_event_str = f"RMS: {last_row.get('rms_v', 0):.4f}V | Missing Time Data"

        except Exception as e:
            # Surface parsing errors directly in the UI to prevent silent failures.
            latest_event_str = f"Parse Error: {str(e)}"
            print(f"Telemetry Parsing Error: {e}")

    # 4. Render the telemetry user interface components.
    with ui.row().classes('w-full gap-4 mt-6 mb-2 items-stretch'):

        # Hardware status display component.
        if hw_status == 'disconnected':
            bg_class = 'bg-red-100 border-red-300 text-red-800'
            icon_name = 'warning'
        else:
            bg_class = 'bg-teal-50 border-teal-200 text-teal-800'
            icon_name = 'settings_input_antenna'

        with ui.card().classes(f'flex-1 p-4 shadow-sm border {bg_class} flex flex-row items-center gap-4'):
            ui.icon(icon_name, size='md')
            with ui.column().classes('gap-0'):
                ui.label("Hardware Status").classes('text-xs uppercase tracking-widest opacity-70')
                ui.label(hw_status.upper()).classes('text-lg font-bold')

        # Patient pain report display component.
        with ui.card().classes(
                'flex-1 p-4 shadow-sm border border-slate-200 bg-white flex flex-row items-center gap-4'):
            ui.icon('personal_injury', size='md').classes('text-slate-400')
            with ui.column().classes('gap-0'):
                ui.label("Latest Pain Report").classes('text-xs text-slate-500 uppercase tracking-widest')
                ui.label(latest_pain).classes('text-lg font-bold text-slate-800')

        # Latest contraction event display component.
        with ui.card().classes(
                'flex-[2] p-4 shadow-sm border border-slate-800 bg-slate-900 text-white flex flex-row items-center gap-4'):
            ui.icon('timeline', size='md').classes('text-teal-400')
            with ui.column().classes('gap-0'):
                ui.label("Latest Contraction Event").classes(
                    'text-xs uppercase tracking-widest opacity-70 text-slate-400')
                ui.label(latest_event_str).classes('text-lg font-mono font-bold text-teal-400')


@ui.refreshable
def render_event_plot(current_session_id):
    """Render a live interactive Plotly scatter plot displaying contraction events."""
    if not os.path.exists('session_history.csv'):
        ui.label("Waiting for the first contraction event to generate the plot...").classes(
            'text-slate-400 italic mt-4')
        return

    try:
        df = pd.read_csv('session_history.csv')
        df_session = df[df['session_id'] == current_session_id].copy()

        if df_session.empty:
            ui.label("Awaiting contraction data for this session...").classes('text-slate-400 italic mt-4')
            return

        df_session['Time'] = pd.to_datetime(df_session['event_id'], unit='s')

        fig = px.scatter(
            df_session,
            x='Time',
            y='rms_v',
            size='burst_duration_sec',
            color='dominant_freq_hz',
            color_continuous_scale=px.colors.sequential.Teal,
            hover_data=['event_id', 'max_amplitude_v'],
            labels={
                "Time": "Time of Event",
                "rms_v": "RMS Power (V)",
                "dominant_freq_hz": "Frequency (Hz)",
                "burst_duration_sec": "Duration (s)",
                "max_amplitude_v": "Max Amp (V)"
            }
        )

        fig.update_layout(
            margin=dict(l=20, r=20, t=20, b=20),
            plot_bgcolor='rgba(248, 250, 252, 1)',
            paper_bgcolor='rgba(255, 255, 255, 0)',
            xaxis_title="Chronological Timeline",
            yaxis_title="Contraction Intensity (RMS V)"
        )

        with ui.card().classes('w-full p-4 shadow-sm border border-slate-200 mt-4'):
            ui.label("Live Contraction Event Analysis").classes('text-lg font-medium text-slate-700 mb-2')
            ui.plotly(fig).classes('w-full h-96')

    except Exception as e:
        ui.label(f"Error generating plot: {e}").classes('text-red-500 text-sm mt-4')


def render_manager():
    frame('/')
    ui.label("Session Manager").classes('text-2xl font-semibold mb-4 text-slate-800 tracking-tight')

    data_map = load_grouped_patients()

    # Organize configuration cards vertically and centered.
    with ui.column().classes('w-full gap-4 items-center'):

        # 1. Patient Configuration Component.
        with ui.card().classes('w-full max-w-sm p-4 shadow-sm border border-slate-200'):
            ui.label("Patient Configuration").classes('text-md font-medium mb-2 text-slate-700')

            # Primary diagnosis selection to filter the subsequent patient list.
            diag_select = ui.select(list(data_map.keys()), label="Select Diagnostic Group").classes('w-full')

            # Patient selection dropdown supporting text filtering.
            pt_select = ui.select([], label="Select Patient ID", with_input=True).classes('w-full')

            # Update logic for the patient selection list based on diagnostic grouping.
            def update_pt_list():
                patients = data_map.get(diag_select.value, [])
                pt_select.options = ["-- Create New Patient --"] + patients
                pt_select.value = pt_select.options[0]

            diag_select.on_value_change(update_pt_list)

            # Input fields for new patient registration.
            with ui.column().classes('w-full gap-1 mt-2').bind_visibility_from(pt_select, 'value',
                                                                               value="-- Create New Patient --"):
                new_pt_input = ui.input("Patient ID").classes('w-full')
                new_pt_pin = ui.input("Set 4-Digit PIN", password=True).classes('w-full')
                new_diagnosis = ui.select(["Healthy", "Endometriosis", "Adenomyosis", "Dysmenorrhea"],
                                          value="Healthy", label="Diagnosis").classes('w-full')

                def save_new_patient():
                    p_id = new_pt_input.value.strip()
                    if not p_id:
                        ui.notify("Please enter a Patient ID", type='negative')
                        return
                    db_cloud.collection('patients').document(p_id).set({
                        "diagnosis": new_diagnosis.value,
                        "pin": new_pt_pin.value
                    })
                    ui.notify(f"Patient {p_id} created successfully!", type='positive')
                    # Force interface refresh to reflect new data.
                    ui.navigate.reload()

                ui.button("Save New Patient", on_click=save_new_patient).classes('w-full bg-teal-600 text-white mt-2')

            # Display elements for existing patient records.
            existing_diagnosis = ui.label().classes(
                'text-sm font-semibold text-slate-600 bg-slate-100 p-2 rounded w-full mt-2')

            def update_diagnosis_display():
                if pt_select.value and pt_select.value != "-- Create New Patient --":
                    existing_diagnosis.set_text(f"Diagnosis: {diag_select.value}")
                    existing_diagnosis.set_visibility(False)
                else:
                    existing_diagnosis.set_visibility(False)

            pt_select.on_value_change(update_diagnosis_display)

        # 2. Mobile Data Sync Component (Hidden for new or unselected patients).
        with ui.card().classes('w-full max-w-sm p-4 shadow-sm border border-slate-200').bind_visibility_from(
                pt_select, 'value', backward=lambda v: bool(v) and v != "-- Create New Patient --"):
            ui.label("Mobile Data Sync").classes('text-md font-medium mb-2 text-slate-700')
            cycle_display = ui.label("Cycle Day: Unknown").classes(
                'text-sm font-semibold text-slate-600 bg-slate-100 p-2 rounded w-full text-center border border-slate-200'
            )

            def fetch_patient_cycle_data():
                pt_id = pt_select.value
                if pt_id and pt_id != "-- Create New Patient --":
                    pt_doc = db_cloud.collection('patients').document(pt_id).get()
                    if pt_doc.exists:
                        data = pt_doc.to_dict()
                        day = data.get('current_cycle_day')
                        if day:
                            cycle_display.set_text(f"Cycle Day: {day} (Synced from App)")
                            cycle_display.classes(
                                replace='text-sm font-semibold text-teal-800 bg-teal-50 p-2 rounded w-full text-center border border-teal-200')
                            return
                cycle_display.set_text("Cycle Day: Unknown (Not Synced)")
                cycle_display.classes(
                    replace='text-sm font-semibold text-slate-600 bg-slate-100 p-2 rounded w-full text-center border border-slate-200')

            pt_select.on_value_change(fetch_patient_cycle_data)
            ui.timer(5.0, fetch_patient_cycle_data)

    ui.separator().classes('my-6 opacity-50')

    # Active Session Dashboard
    status_container = ui.column().classes('w-full items-center p-4')

    def refresh_status():
        status_container.clear()
        ctrl = read_session_control()
        is_running = ctrl.get("is_running", False)

        with status_container:
            if not is_running:
                def start_session():
                    selected = pt_select.value
                    if not selected or selected == "-- Create New Patient --":
                        ui.notify("Please select or save a patient first.", type='warning')
                        return

                    sess_id = f"SES_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                    db_cloud.collection('patients').document(selected).collection('sessions').document(sess_id).set({
                        "started_at": time.time(),
                        "diagnosis": diag_select.value or "Unknown"
                    })

                    new_ctrl = {"is_running": True, "patient_id": selected, "session_id": sess_id}
                    with open("session_control.json", "w") as f:
                        json.dump(new_ctrl, f)
                    ui.notify("Session started.", type='positive')
                    refresh_status()

                ui.button("Start Data Collection", on_click=start_session).classes(
                    'w-full max-w-sm bg-slate-800 text-white font-medium py-2')

            else:
                with ui.row().classes('w-full justify-between items-center mb-4'):
                    ui.label(f"Recording: {ctrl['patient_id']} | {ctrl['session_id']}").classes(
                        'text-slate-800 text-xl font-bold')

                    def stop_session():
                        ctrl["is_running"] = False
                        with open("session_control.json", "w") as f:
                            json.dump(ctrl, f)
                        clear_cohort_vault()
                        ui.notify("Session concluded.", type='info')
                        refresh_status()

                    ui.button("End Session", on_click=stop_session).classes(
                        'bg-red-700 text-white font-medium py-2 px-8')

                # Live Telemetry Console Initialization
                render_telemetry_console(ctrl['session_id'], ctrl['patient_id'])
                ui.timer(3.0,
                         lambda sid=ctrl['session_id'], pid=ctrl['patient_id']: render_telemetry_console.refresh(sid,
                                                                                                                 pid))

                # Live Contraction Scatter Plot Initialization
                render_event_plot(ctrl['session_id'])
                ui.timer(3.0, lambda sid=ctrl['session_id']: render_event_plot.refresh(sid))

    refresh_status()