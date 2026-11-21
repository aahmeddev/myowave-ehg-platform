import json
import os
import shutil

from nicegui import app, ui
from page_cohort import render_cohort
from page_export import render_export
from page_manager import render_manager
from page_patient import render_patient

ADMIN_PASSWORD = os.environ.get("MYOWAVE_ADMIN_PASSWORD", "endo1000_admin")
STORAGE_SECRET = os.environ.get("MYOWAVE_STORAGE_SECRET", "myowave_dev_storage_secret")


def check_auth() -> None:
    """Redirect unauthenticated sessions to the researcher login page."""
    if not app.storage.user.get("authenticated", False):
        ui.navigate.to("/login")


@ui.page("/login")
def login_page() -> None:
    def try_login() -> None:
        if password.value == ADMIN_PASSWORD:
            app.storage.user["authenticated"] = True
            ui.navigate.to("/")
        else:
            ui.notify("Unauthorised access", type="negative")

    with ui.card().classes("absolute-center w-96 p-6 shadow-md border-t-4 border-slate-800"):
        ui.label("Clinical Researcher Portal").classes("text-xl font-bold mb-2 text-slate-800")
        ui.label("Please authenticate to view sensitive EHG data.").classes("text-sm text-slate-500 mb-6")
        password = ui.input("Master Password", password=True).classes("w-full mb-6")
        ui.button("Secure Log In", on_click=try_login).classes("w-full bg-slate-800 text-white py-2")


@ui.page("/")
def index() -> None:
    check_auth()
    render_manager()


@ui.page("/cohort")
def cohort() -> None:
    check_auth()
    render_cohort()


@ui.page("/patient")
def patient() -> None:
    check_auth()
    render_patient()


@ui.page("/export")
def export() -> None:
    check_auth()
    render_export()


def force_session_stop() -> None:
    """Ensure the hardware DAQ loop is explicitly stopped on startup and shutdown."""
    try:
        with open("session_control.json", "w", encoding="utf-8") as f:
            json.dump({"is_running": False}, f)
    except OSError:
        pass


app.on_startup(force_session_stop)
app.on_shutdown(force_session_stop)

if __name__ in {"__main__", "__mp_main__"}:
    if os.path.exists(".nicegui"):
        try:
            shutil.rmtree(".nicegui")
        except OSError as exc:
            print(f"Notice: Could not clear old session data: {exc}")

    ui.run(
        title="Researcher Portal",
        port=8081,
        dark=False,
        reload=False,
        storage_secret=STORAGE_SECRET,
    )
