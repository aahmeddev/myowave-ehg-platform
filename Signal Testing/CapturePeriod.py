import serial
import csv
import matplotlib.pyplot as plt
import time
import sys

# Configuration Parameters
PORT = 'COM3'
BAUD = 115200
FS = 250  # Sampling frequency in Hz.
IGNORE_SEC = 10  # Hardware stabilization buffer period.
RECORD_SEC = 60  # Active data acquisition duration.
TOTAL_SAMPLES = FS * RECORD_SEC

recorded_data = []

try:
    ser = serial.Serial(PORT, BAUD, timeout=1)
    ser.reset_input_buffer()
    print(f"Connected to {PORT}.")
except Exception as e:
    print(f"Error: {e}")
    sys.exit()

# 1. Hardware Stabilization Phase (Purge initial uncalibrated data).
print(f"Phase 1: Stabilizing for {IGNORE_SEC} seconds...")
start_warmup = time.time()
while time.time() - start_warmup < IGNORE_SEC:
    if ser.in_waiting > 0:
        ser.readline()  # Discard incoming data until baseline equilibrium is reached.

# 2. Data Acquisition Phase (Capture 60 seconds of steady-state data).
print(f"Phase 2: Recording for {RECORD_SEC} seconds ({TOTAL_SAMPLES} samples)...")
try:
    while len(recorded_data) < TOTAL_SAMPLES:
        if ser.in_waiting > 0:
            line_raw = ser.readline().decode('utf-8').strip()
            if line_raw:
                try:
                    val = float(line_raw)
                    recorded_data.append(val)

                    # Output acquisition progress at 5-second intervals.
                    if len(recorded_data) % (FS * 5) == 0:
                        progress = (len(recorded_data) / TOTAL_SAMPLES) * 100
                        print(f"Progress: {progress:.0f}%")
                except ValueError:
                    continue
except KeyboardInterrupt:
    print("\nRecording aborted by user.")

# 3. Data Persistence Phase
filename = "ehg_capture_1min.csv"
with open(filename, 'w', newline='') as f:
    writer = csv.writer(f)
    writer.writerow(["Sample", "Voltage_V"])
    for i, val in enumerate(recorded_data):
        writer.writerow([i, val])

print(f"Done! Data saved to {filename}")

# 4. Visualization Phase
plt.figure(figsize=(15, 6))
plt.plot(recorded_data, color='darkred', lw=0.8)
plt.title("EHG 60-Second Capture (Post-Stabilization)")
plt.xlabel("Samples")
plt.ylabel("Voltage (V)")
plt.grid(True, alpha=0.3)
plt.tight_layout()
plt.show()

ser.close()