import os
import shutil
import json
from nicegui import ui, app
from page_manager import render_manager
from page_cohort import render_cohort
from page_patient import render_patient
from page_export import render_export


# 1. Authentication Gatekeeper
def check_auth():
    if not app.storage.user.get('authenticated', False):
        ui.navigate.to('/login')


# 2. Login Page
@ui.page('/login')
def login_page():
    def try_login():
        if password.value == 'endo1000_admin':
            app.storage.user['authenticated'] = True
            ui.navigate.to('/')
        else:
            ui.notify('Unauthorized Access', type='negative')

    with ui.card().classes('absolute-center w-96 p-6 shadow-md border-t-4 border-slate-800'):
        ui.label('Clinical Researcher Portal').classes('text-xl font-bold mb-2 text-slate-800')
        ui.label('Please authenticate to view sensitive EHG data.').classes('text-sm text-slate-500 mb-6')
        password = ui.input('Master Password', password=True).classes('w-full mb-6')
        ui.button('Secure Log In', on_click=try_login).classes('w-full bg-slate-800 text-white py-2')


# 3. Protected Routes
@ui.page('/')
def index():
    check_auth()
    render_manager()


@ui.page('/cohort')
def cohort():
    check_auth()
    render_cohort()


@ui.page('/patient')
def patient():
    check_auth()
    render_patient()


@ui.page('/export')
def export():
    render_export()


# Lifecycle Failsafes
def force_session_stop():
    """Ensure the hardware DAQ loop is explicitly terminated."""
    try:
        with open("session_control.json", "w") as f:
            json.dump({"is_running": False}, f)
    except Exception:
        pass


# Trigger the failsafe during server startup and shutdown events.
app.on_startup(force_session_stop)
app.on_shutdown(force_session_stop)

if __name__ in {"__main__", "__mp_main__"}:

    # Clear physical cookie records to ensure all users are logged out upon server initialization.
    if os.path.exists('.nicegui'):
        try:
            shutil.rmtree('.nicegui')
        except Exception as e:
            print(f"Notice: Could not clear old session data: {e}")

    ui.run(title="Researcher Portal", port=8081, dark=False, reload=False, storage_secret='myowave_secure_key_2026')