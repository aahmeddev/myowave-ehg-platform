from nicegui import ui, run, app
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from page_cohort import clear_cohort_vault
import sqlite3

# Dependency Resolution
from google.cloud.firestore_v1.base_query import FieldFilter

from config_db import init_firebase, DB_NAME
from layout import frame

# Initialize Firebase connection.
db_cloud = init_firebase()


def get_patient_ids():
    """Retrieve patient ID strings from the database."""
    docs = db_cloud.collection('patients').stream()
    return [doc.id for doc in docs]


def fetch_patient_events(pt_id):
    """Execute a targeted NoSQL query to retrieve data specific to the provided patient ID."""
    events_data = []

    # Utilize modern FieldFilter to resolve Google Cloud UserWarnings.
    events = db_cloud.collection_group('events').where(filter=FieldFilter('patient_id', '==', pt_id)).stream()

    for ev in events:
        events_data.append(ev.to_dict())
    return pd.DataFrame(events_data)


def delete_patient_records(pt_id):
    """Permanently delete all patient records from local SQLite and cloud Firestore databases."""
    try:
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute("DELETE FROM processed_events WHERE session_id LIKE ?", (f"{pt_id}%",))
        c.execute("DELETE FROM raw_contractions WHERE patient_id = ?", (pt_id,))
        c.execute("DELETE FROM patients WHERE patient_id = ?", (pt_id,))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Local DB deletion error: {e}")

    try:
        sessions_ref = db_cloud.collection('patients').document(pt_id).collection('sessions')
        for session in sessions_ref.stream():
            for event in session.reference.collection('events').stream():
                event.reference.delete()
            for pain in session.reference.collection('pain_logs').stream():
                pain.reference.delete()
            session.reference.delete()

        db_cloud.collection('patients').document(pt_id).delete()
    except Exception as e:
        print(f"Cloud DB deletion error: {e}")

    clear_cohort_vault()

    if 'cohort_df' in app.storage.client:
        del app.storage.client['cohort_df']

    ui.notify(f"All records for {pt_id} have been permanently deleted.", type='positive')
    ui.timer(1.0, ui.navigate.reload, once=True)


def render_patient():
    """Render the primary Patient Clinical Analysis dashboard."""
    frame('/patient')
    ui.label("Patient Clinical Analysis").classes('text-2xl font-semibold mb-2 text-slate-800 tracking-tight')
    ui.label("Longitudinal tracking and specific event analysis.").classes('mb-8 text-slate-600')

    patients = get_patient_ids()
    if not patients:
        ui.label("No data found in Firebase.").classes('text-slate-500 italic')
        return

    with ui.row().classes('w-full items-center gap-4 mb-8'):
        selected_pt = ui.select(patients, value=patients[0], label="Patient ID").classes('w-1/4')

        def confirm_delete():
            pt_id = selected_pt.value
            if not pt_id: return
            with ui.dialog() as dialog, ui.card().classes('p-6'):
                ui.label(f'Are you sure you want to permanently delete {pt_id}?').classes(
                    'text-lg font-bold text-slate-800 mb-2')
                ui.label(
                    'This will remove all records from the local system and the cloud. This action cannot be undone.').classes(
                    'text-sm text-slate-600 mb-6')
                with ui.row().classes('w-full justify-end gap-2'):
                    ui.button('Cancel', on_click=dialog.close).classes('bg-slate-200 text-slate-800')
                    ui.button('Delete Records', color='red',
                              on_click=lambda: (delete_patient_records(pt_id), dialog.close()))
            dialog.open()

        ui.button("Delete Patient", color='red-7', icon='delete_forever', on_click=confirm_delete).props('outline')

    content_container = ui.column().classes('w-full')

    async def update_dashboard():
        content_container.clear()
        pt_id = selected_pt.value
        if not pt_id: return

        with content_container:
            spinner = ui.spinner('dots', size='lg').classes('mt-10 mx-auto text-slate-400')

            df_pt = await run.io_bound(fetch_patient_events, pt_id)

            content_container.remove(spinner)

            df_pt = df_pt[df_pt['dominant_freq_hz'] > 0.0].copy()

            if df_pt.empty:
                ui.label(f"No valid physiological events recorded for {pt_id}.").classes('text-slate-500 italic mt-4')
                return

            df_pt['datetime'] = pd.to_datetime(df_pt['timestamp_start'], unit='s')
            df_pt = df_pt.sort_values('datetime')

            if 'power_fwl' not in df_pt.columns: df_pt['power_fwl'] = 0.0
            if 'power_fwh' not in df_pt.columns: df_pt['power_fwh'] = 0.0
            if 'cycle_day' not in df_pt.columns: df_pt['cycle_day'] = 0
            if 'pain_scale' not in df_pt.columns: df_pt['pain_scale'] = 0.0
            if 'diagnosis' not in df_pt.columns: df_pt['diagnosis'] = 'Unknown'

            session_summary = df_pt.groupby(['session_id']).agg({
                'datetime': 'min',
                'cycle_day': 'first',
                'pain_scale': 'first',
                'diagnosis': 'first',
                'event_id': 'count',
                'rms_v': 'mean',
                'dominant_freq_hz': 'mean',
                'power_fwh': 'mean',
                'power_fwl': 'mean'
            }).reset_index().sort_values('datetime')

            df_pt['date'] = df_pt['datetime'].dt.floor('D')
            daily_summary = df_pt.groupby('date').agg({
                'dominant_freq_hz': 'mean',
                'rms_v': 'mean'
            }).reset_index().sort_values('date')

            daily_summary['freq_ma'] = daily_summary['dominant_freq_hz'].rolling(window=3, min_periods=1).mean()
            daily_summary['rms_ma'] = daily_summary['rms_v'].rolling(window=3, min_periods=1).mean()

            # 1. Expanded Patient Profile Rendering
            ui.label("Clinical Profile").classes('text-lg font-medium mb-4 text-slate-700 border-b pb-2 w-full')
            with ui.row().classes('w-full gap-4 mb-8'):
                metrics = [
                    ("Diagnosis", str(session_summary['diagnosis'].iloc[0])),
                    ("Recorded Sessions", str(len(session_summary))),
                    ("Total Contractions", str(len(df_pt))),
                    ("Current Pain Score", f"{session_summary['pain_scale'].iloc[-1]} / 10"),
                    ("Current Cycle Day", str(session_summary['cycle_day'].iloc[-1]))
                ]
                for title, value in metrics:
                    with ui.card().classes('flex-1 p-4 shadow-sm bg-slate-50 border border-slate-200'):
                        ui.label(title).classes('text-xs text-slate-500 uppercase tracking-wider')
                        ui.label(value).classes('text-xl font-bold text-slate-800')

            # 2. Longitudinal Trend Charts Rendering
            ui.label("Longitudinal Trends").classes('text-lg font-medium mt-4 mb-4 text-slate-700 border-b pb-2 w-full')
            with ui.row().classes('w-full gap-8 mb-8'):
                with ui.column().classes('w-1/2 flex-grow'):
                    fig_time = go.Figure()

                    fig_time.add_trace(
                        go.Scatter(x=df_pt['datetime'], y=df_pt['dominant_freq_hz'], mode='markers', name='Raw Freq',
                                   marker=dict(color='#0ea5e9', size=4, opacity=0.15), showlegend=False))
                    fig_time.add_trace(go.Scatter(x=daily_summary['date'], y=daily_summary['freq_ma'], mode='lines',
                                                  name='Freq 3-Day Avg (Hz)',
                                                  line=dict(color='#0ea5e9', width=3, shape='spline')))

                    fig_time.add_trace(
                        go.Scatter(x=df_pt['datetime'], y=df_pt['rms_v'], mode='markers', name='Raw Intensity',
                                   yaxis='y2', marker=dict(color='#0f172a', size=4, opacity=0.15), showlegend=False))
                    fig_time.add_trace(go.Scatter(x=daily_summary['date'], y=daily_summary['rms_ma'], mode='lines',
                                                  name='Intensity 3-Day Avg (RMS)', yaxis='y2',
                                                  line=dict(color='#0f172a', width=3, shape='spline')))

                    fig_time.update_layout(
                        margin=dict(l=20, r=20, t=30, b=20),
                        xaxis_title="Date",
                        yaxis=dict(title=dict(text="Frequency (Hz)", font=dict(color="#0ea5e9")),
                                   tickfont=dict(color="#0ea5e9")),
                        yaxis2=dict(title=dict(text="Intensity (V)", font=dict(color="#0f172a")),
                                    tickfont=dict(color="#0f172a"), anchor="x", overlaying="y", side="right"),
                        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
                    )
                    ui.plotly(fig_time).classes('w-full border border-slate-200 rounded')

                with ui.column().classes('w-1/2 flex-grow'):
                    df_power = session_summary.melt(id_vars=['cycle_day'], value_vars=['power_fwl', 'power_fwh'],
                                                    var_name='Band', value_name='Power')
                    fig_cycle = px.bar(df_power, x='cycle_day', y='Power', color='Band', barmode='group',
                                       color_discrete_map={'power_fwl': '#94a3b8', 'power_fwh': '#0f172a'})
                    fig_cycle.update_layout(margin=dict(l=20, r=20, t=30, b=20))
                    ui.plotly(fig_cycle).classes('w-full border border-slate-200 rounded')

            # 3. Synchronized Event Telemetry Rendering
            ui.label("Contraction Event Telemetry").classes(
                'text-lg font-medium mt-8 mb-4 text-slate-700 border-b pb-2 w-full')
            ui.label(
                "Synchronized metric density. Translucent overlays highlight regions of high physiological activity.").classes(
                'text-sm text-slate-500 mb-4')

            try:
                fig_separated = make_subplots(rows=4, cols=1, shared_xaxes=True, vertical_spacing=0.05,
                                              subplot_titles=("RMS Power (V)", "Dominant Frequency (Hz)",
                                                              "Burst Duration (s)", "Max Amplitude (V)"))
                fig_separated.add_trace(
                    go.Scatter(x=df_pt['datetime'], y=df_pt['rms_v'], mode='markers', name='RMS (V)',
                               marker=dict(size=8, color='#0f172a', opacity=0.4)), row=1, col=1)
                fig_separated.add_trace(
                    go.Scatter(x=df_pt['datetime'], y=df_pt['dominant_freq_hz'], mode='markers', name='Freq (Hz)',
                               marker=dict(size=8, color='#0ea5e9', opacity=0.4)), row=2, col=1)
                fig_separated.add_trace(
                    go.Scatter(x=df_pt['datetime'], y=df_pt['burst_duration_sec'], mode='markers', name='Duration (s)',
                               marker=dict(size=8, color='#14b8a6', opacity=0.4)), row=3, col=1)
                fig_separated.add_trace(
                    go.Scatter(x=df_pt['datetime'], y=df_pt['max_amplitude_v'], mode='markers', name='Max Amp (V)',
                               marker=dict(size=8, color='#64748b', opacity=0.4)), row=4, col=1)

                fig_separated.update_layout(height=800, showlegend=False, margin=dict(l=20, r=20, t=40, b=20),
                                            plot_bgcolor='rgba(248, 250, 252, 1)',
                                            paper_bgcolor='rgba(255, 255, 255, 0)', hovermode="x unified")
                fig_separated.update_xaxes(title_text="Chronological Timeline", row=4, col=1)

                with ui.card().classes('w-full p-4 shadow-sm border border-slate-200 mt-4'):
                    ui.plotly(fig_separated).classes('w-full h-[800px]')

            except Exception as e:
                ui.label(f"Error generating separated plots: {e}").classes('text-red-500 text-sm mt-4')

    selected_pt.on_value_change(update_dashboard)
    ui.timer(0, update_dashboard, once=True)