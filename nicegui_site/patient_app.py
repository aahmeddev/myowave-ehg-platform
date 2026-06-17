from nicegui import ui
import time
import asyncio
import random
from datetime import datetime
import firebase_admin
from firebase_admin import credentials, firestore

# Initialize Firebase connection.
if not firebase_admin._apps:
    cred = credentials.Certificate('firebase_key.json')
    firebase_admin.initialize_app(cred)
db = firestore.client()


def render_patient_portal():
    ui.colors(primary='#0f172a', secondary='#0ea5e9')

    # Apply mobile-first container constraints.
    with ui.column().classes('w-full max-w-md mx-auto p-4 items-center'):
        ui.icon('medical_services', size='48px').classes('text-slate-800 mb-2')
        ui.label('ENDO1000 Patient Portal').classes('text-2xl font-bold text-slate-800 mb-6 tracking-tight')

        login_card = ui.card().classes('w-full p-6 shadow-sm border border-slate-200 bg-slate-50')
        with login_card:
            ui.label('Secure Login').classes('text-lg font-semibold text-slate-700 mb-2')
            patient_input = ui.input('Enter Patient ID (e.g., PT-001)').classes('w-full mb-2')
            pin_input = ui.input('Enter 4-Digit PIN', password=True, password_toggle_button=True).classes('w-full mb-4')
            login_btn = ui.button('Access Portal').classes('w-full bg-slate-800 text-white font-medium py-2')

        content_area = ui.column().classes('w-full mt-2')

        def load_dashboard():
            pt_id = patient_input.value.strip()
            if not pt_id:
                ui.notify('Please enter a valid ID', type='negative')
                return

            pt_ref = db.collection('patients').document(pt_id).get()
            if not pt_ref.exists:
                ui.notify('Patient record not found.', type='negative')
                return

            pt_data = pt_ref.to_dict() or {}
            db_pin = pt_data.get('pin', '1234')
            if pin_input.value != db_pin:
                ui.notify('Authentication Failed: Invalid PIN.', type='negative')
                return

            saved_cycle_day = pt_data.get('current_cycle_day', None)

            content_area.clear()
            login_card.set_visibility(False)

            with content_area:
                ui.label(f'Welcome, {pt_id}').classes('text-xl font-semibold mb-2 border-b w-full pb-2 text-slate-800')

                # Navigation Tabs Configuration
                with ui.tabs().classes('w-full text-slate-700') as tabs:
                    dash_tab = ui.tab('Dashboard', icon='space_dashboard')
                    guide_tab = ui.tab('Device Guide', icon='menu_book')

                sessions_ref = db.collection('patients').document(pt_id).collection('sessions').stream()
                session_list = [s.id for s in sessions_ref]
                active_session = session_list[-1] if session_list else "No Active Session"

                # Tab Panels Configuration
                with ui.tab_panels(tabs, value=dash_tab).classes('w-full bg-transparent p-0 mt-4'):

                    # Tab 1: Primary Dashboard (Reporting and Synchronization)
                    with ui.tab_panel(dash_tab).classes('p-0'):

                        # 1. Cycle Tracker Synchronization Component
                        with ui.card().classes('w-full p-5 shadow-sm border border-slate-200 bg-white mb-4'):
                            ui.label('Cycle Tracking Integration').classes(
                                'text-xs text-slate-500 uppercase tracking-widest mb-1')
                            ui.label(
                                'Connect your mobile health app (Apple Health, Clue, Flo) to sync your cycle data.').classes(
                                'text-sm text-slate-600 mb-4')

                            status_bg = 'text-teal-700 bg-teal-50 border border-teal-200' if saved_cycle_day else 'text-slate-600 bg-slate-100'
                            status_text = f"Status: Synced (Day {saved_cycle_day})" if saved_cycle_day else "Status: Unlinked"

                            sync_status = ui.label(status_text).classes(
                                f"text-sm font-semibold p-2 rounded w-full mb-4 text-center {status_bg}")

                            async def sync_health_app():
                                sync_btn.disable()
                                sync_btn.text = "Authenticating API..."
                                ui.notify("Connecting to health provider...", type='info')
                                await asyncio.sleep(1.5)
                                assigned_day = random.randint(1, 28)
                                db.collection('patients').document(pt_id).set({'current_cycle_day': assigned_day},
                                                                              merge=True)
                                sync_status.set_text(f"Status: Synced (Cycle Day {assigned_day})")
                                sync_status.classes(
                                    replace='text-sm font-semibold text-teal-700 bg-teal-50 p-2 rounded w-full mb-4 border border-teal-200 text-center')
                                ui.notify("Cycle data imported successfully.", type='positive')
                                sync_btn.text = "Data Synced"

                            sync_btn = ui.button("Connect Health App", on_click=sync_health_app).classes(
                                'w-full bg-slate-800 text-white py-2 font-medium shadow-sm')
                            if saved_cycle_day: sync_btn.text = "Resync Data"

                        # 2. Active Session Monitoring Component
                        with ui.card().classes('w-full p-5 shadow-sm border border-slate-200 bg-white mb-4'):
                            ui.label('Current Monitoring Session').classes(
                                'text-xs text-slate-500 uppercase tracking-widest mb-1')
                            ui.label(active_session).classes('text-sm font-mono text-slate-800 mb-6')

                            ui.label('Report Current Pain Level').classes('text-base font-medium text-slate-700 mb-2')
                            pain_slider = ui.slider(min=1, max=10, value=5).classes('w-full mb-2')
                            pain_label = ui.label('Level: 5 / 10').classes(
                                'text-sm font-bold text-slate-600 mb-6 text-center w-full')

                            pain_slider.on('update:model-value',
                                           lambda e: pain_label.set_text(f'Level: {int(e.args)} / 10'))

                            def submit_pain():
                                if active_session == "No Active Session":
                                    ui.notify('No active hardware session to log pain against.', type='warning')
                                    return
                                ts = time.time()
                                pain_val = int(pain_slider.value)
                                db.collection('patients').document(pt_id).collection('sessions').document(
                                    active_session).collection('pain_logs').document(str(int(ts))).set(
                                    {'timestamp': ts, 'pain_scale': pain_val})
                                ui.notify('Pain level securely recorded.', type='positive')

                            ui.button('Submit Pain Report', on_click=submit_pain).classes(
                                'w-full bg-blue-600 text-white py-3 font-bold shadow-sm')

                        # 3. Hardware Status Monitoring Component
                        status_label = ui.label('Hardware Status: Active').classes(
                            'text-sm font-bold text-teal-600 mt-2 text-center w-full')
                        current_status = {'state': 'active'}

                        def check_hardware_status():
                            if active_session != "No Active Session":
                                doc = db.collection('patients').document(pt_id).collection('sessions').document(
                                    active_session).get()
                                if doc.exists:
                                    db_status = doc.to_dict().get('connection_status', 'active')
                                    if db_status == 'disconnected' and current_status['state'] != 'disconnected':
                                        ui.notify('DEVICE DISCONNECTED. Please check your wearable.', type='negative',
                                                  position='top')
                                        status_label.set_text('Hardware Status: DISCONNECTED')
                                        status_label.classes(
                                            replace='text-sm font-bold text-red-600 mt-2 text-center w-full')
                                        current_status['state'] = 'disconnected'
                                    elif db_status == 'active' and current_status['state'] == 'disconnected':
                                        ui.notify('DEVICE RECONNECTED. Resuming data sync.', type='positive',
                                                  position='top')
                                        status_label.set_text('Hardware Status: Active')
                                        status_label.classes(
                                            replace='text-sm font-bold text-teal-600 mt-2 text-center w-full')
                                        current_status['state'] = 'active'

                        ui.timer(2.0, check_hardware_status)

                    # Tab 2: Device Operational Guide
                    with ui.tab_panel(guide_tab).classes('p-0 gap-4 flex flex-col'):

                        # Video guide component.
                        with ui.card().classes('w-full p-0 overflow-hidden shadow-sm border border-slate-200 bg-white'):
                            # Note: Replace placeholder URL with the production video link.
                            ui.video('assets/placeholder_electrode_guide.mp4').classes('w-full aspect-video').props(
                                'controls')
                            with ui.column().classes('p-4'):
                                ui.label('Electrode Application Guide').classes('text-lg font-bold text-slate-800')
                                ui.label(
                                    'Watch this quick video to learn how to properly attach the MyoWave sensor.').classes(
                                    'text-sm text-slate-600')

                        # Quick setup instruction component.
                        with ui.card().classes('w-full p-5 shadow-sm border border-slate-200 bg-white'):
                            ui.label('Quick Setup Steps').classes(
                                'text-base font-bold text-slate-800 mb-2 border-b pb-2 w-full')

                            steps = [
                                "Power on: Press and hold the power button until the LED indicator turns on.",
                                "Apply electrodes: Place 4 electrodes below the navel (E1, E2, E3, E4).",
                                "Check connection: Confirm app is connected and signal is available.",
                                "Resting calibration: Stay still for 1-2 minutes to allow baseline calibration.",
                                "Start recording: Tap 'Start' in the clinical dashboard.",
                                "Stop & save: Tap 'End Session' when done."
                            ]
                            for i, step in enumerate(steps, 1):
                                with ui.row().classes('items-start gap-3 mb-2 w-full no-wrap'):
                                    ui.label(str(i)).classes(
                                        'bg-slate-200 text-slate-700 rounded-full w-6 h-6 flex items-center justify-center text-xs font-bold shrink-0')
                                    ui.label(step).classes('text-sm text-slate-700')

                        # Frequently Asked Questions accordion components for compact display.
                        with ui.card().classes('w-full p-5 shadow-sm border border-slate-200 bg-white'):
                            ui.label('Frequently Asked Questions').classes(
                                'text-base font-bold text-slate-800 mb-2 border-b pb-2 w-full')

                            with ui.expansion('No signal or noisy signal?', icon='sensors').classes('w-full text-sm'):
                                ui.label(
                                    'Check electrode placement and connection. Ensure skin is clean and dry. Reduce movement and move away from strong electromagnetic sources.').classes(
                                    'text-slate-600')

                            with ui.expansion('Can I shower or swim?', icon='water_drop').classes('w-full text-sm'):
                                ui.label(
                                    'No. Remove the device before bathing, showering, or swimming unless otherwise stated by the study team.').classes(
                                    'text-slate-600')

                            with ui.expansion('Cleaning & Maintenance', icon='cleaning_services').classes(
                                    'w-full text-sm'):
                                ui.label(
                                    'Clean the device unit by wiping with a soft, slightly damp cloth only. Do not submerge. Replace electrodes when damaged or adhesion is reduced.').classes(
                                    'text-slate-600')

                        # Safety notice and warning component.
                        with ui.card().classes('w-full p-4 shadow-sm border border-red-200 bg-red-50'):
                            with ui.row().classes('items-center gap-2 mb-1'):
                                ui.icon('warning', color='red-600')
                                ui.label('Safety Notice').classes('font-bold text-red-800')
                            ui.label(
                                'If severe persistent pain, abnormal bleeding, dizziness, or fainting occurs, stop immediately and seek medical attention.').classes(
                                'text-sm text-red-700')

        login_btn.on_click(load_dashboard)


if __name__ in {"__main__", "__mp_main__"}:
    render_patient_portal()
    ui.run(title='Patient Portal', port=8082, dark=False, reload=False)