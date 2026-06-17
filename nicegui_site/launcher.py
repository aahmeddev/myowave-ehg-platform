import subprocess
import sys
import time
import os


def start_system():
    print("Starting MYOWAVE EHG Capture System...\n")

    processes = []

    # Flag to open a new terminal window on Windows for Cloudflare URLs.
    CREATE_NEW_CONSOLE = 0x00000010 if os.name == 'nt' else 0

    try:
        # 1. Initialize the Hardware DAQ Service.
        print("-> Launching DAQ Service (background_service.py)...")
        daq_process = subprocess.Popen([sys.executable, "background_service.py"])
        processes.append(daq_process)
        time.sleep(1)  # Allow hardware initialization time.

        # 2. Initialize the Researcher Portal on Port 8081.
        print("-> Launching Researcher Portal (dashboard.py | Port 8081)...")
        researcher_process = subprocess.Popen([sys.executable, "dashboard.py"])
        processes.append(researcher_process)

        # 3. Initialize the Patient Portal on Port 8082.
        print("-> Launching Patient Portal (patient_app.py | Port 8082)...")
        patient_process = subprocess.Popen([sys.executable, "patient_app.py"])
        processes.append(patient_process)

        # 4. Initialize Cloudflare Quick Tunnels in separate instances.
        print("-> Launching Cloudflare Quick Tunnels...")
        tunnel_res = subprocess.Popen(
            ["cloudflared.exe", "tunnel", "--url", "http://localhost:8081"],
            creationflags=CREATE_NEW_CONSOLE
        )
        processes.append(tunnel_res)

        tunnel_pat = subprocess.Popen(
            ["cloudflared.exe", "tunnel", "--url", "http://localhost:8082"],
            creationflags=CREATE_NEW_CONSOLE
        )
        processes.append(tunnel_pat)

        print("\n=== ALL SYSTEMS ACTIVE ===")
        print("Local Researcher Access: http://localhost:8081")
        print("Local Patient Access:    http://localhost:8082")
        print("\n>>> LOOK FOR TWO NEW WINDOWS! <<<")
        print("They contain your public 'trycloudflare.com' links.")
        print("\nPress Ctrl+C in this terminal to shut down securely.\n")

        # Maintain the main process while background services are active.
        while True:
            time.sleep(1)

    except KeyboardInterrupt:
        print("\nShutting down all MYOWAVE services (including tunnels)...")
        for p in processes:
            p.terminate()

        # Await graceful termination of all subprocesses.
        for p in processes:
            p.wait()

        print("System safely shut down.")


if __name__ == "__main__":
    start_system()