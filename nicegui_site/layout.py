from nicegui import ui, app
import json
import os


def frame(active_path='/'):
    """
    Render the shared navigation header for all web application pages.
    Requires the current path to highlight the active tab accurately.
    """
    with ui.header().classes('w-full bg-slate-900 text-white p-4 flex justify-between items-center shadow-md'):

        # Interface Header: Logo and Title
        with ui.row().classes('items-center gap-2'):
            ui.icon('monitor_heart', size='md').classes('text-teal-400')
            ui.label('MYOWAVE EHG Biosensor Platform').classes('text-xl font-bold tracking-wider')

        # Interface Header: Navigation and Authentication
        with ui.row().classes('gap-6 text-sm font-medium uppercase tracking-widest items-center'):
            nav_links = [
                ('Session Manager', '/'),
                ('Cohort Dashboard', '/cohort'),
                ('Patient Analysis', '/patient'),
                ('Export', '/export')
            ]

            for name, path in nav_links:
                if path == active_path:
                    ui.link(name, path).classes('text-teal-400 font-bold no-underline pointer-events-none')
                else:
                    ui.link(name, path).classes(
                        'text-slate-300 hover:text-teal-400 transition-colors duration-200 no-underline')

            # Authentication Logout Routine
            def logout():
                # 1. Terminate the background DAQ service recording.
                try:
                    with open('session_control.json', 'w') as f:
                        json.dump({"is_running": False}, f)
                except Exception as e:
                    print(f"Error terminating session on logout: {e}")

                # 2. Clear browser authentication storage.
                app.storage.user.clear()
                ui.navigate.to('/login')
                ui.notify('Signed out and active session terminated.', type='info')

            ui.label('|').classes('text-slate-700 ml-2')

            ui.button('Sign Out', icon='logout', on_click=logout).classes(
                'bg-slate-800 hover:bg-slate-700 text-red-400 px-4 py-1 shadow-none border border-slate-700'
            ).props('dense')

    ui.add_head_html('''
        <style>
            body { background-color: #f8fafc; }
            * { -ms-overflow-style: none !important; scrollbar-width: none !important; }
            *::-webkit-scrollbar { display: none !important; width: 0 !important; height: 0 !important; }
        </style>
    ''')