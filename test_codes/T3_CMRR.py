import serial
import time
import numpy as np
import pandas as pd

# Interference Rejection Configuration
PORT = 'COM3'
BAUD = 115200
TEST_DURATION = 12  # Comprises a 2-second initial buffer coupled with a 10-second active testing period.
EXPECTED_V_IN = 1.074  # Calibrated peak-to-peak reference voltage established during preliminary bandwidth testing.
DIFFERENTIAL_GAIN = 24.0  # Hardware differential gain configuration applied specifically for the active ADS1299 channel.


def run_cmrr_test():
    try:
        ser = serial.Serial(PORT, BAUD, timeout=0.1)
        print(f"Connected to {PORT}.")
    except Exception as e:
        print(f"Hardware Error: {e}")
        return

    input("\nEnsure DAC0 is connected to BOTH IN1P and IN1N. Press ENTER to start...")
    print(f"Recording 50Hz interference for {TEST_DURATION} seconds...", flush=True)

    data = []
    start_time = time.time()
    ser.reset_input_buffer()

    while (time.time() - start_time) < TEST_DURATION:
        if ser.in_waiting > 0:
            line = ser.readline().decode('utf-8', errors='ignore').strip()
            if line:
                try:
                    voltage_val = float(line)
                    data.append(voltage_val)
                except ValueError:
                    continue

    ser.close()

    # Discard the initial 2 seconds of recorded data to permit AC coupling capacitor stabilization.
    settled_data = data[int(250 * 2):]

    if len(settled_data) == 0:
        print("No data received.")
        return

    v_max = np.max(settled_data)
    v_min = np.min(settled_data)
    v_out_cm = v_max - v_min

    print("\n" + "=" * 40)
    print("TEST 1.2: CMRR RESULTS")
    print("=" * 40)

    print(f"Common-Mode Input Voltage (V_in): {EXPECTED_V_IN:.4f} V")
    print(f"Measured Leakage Voltage (V_out): {v_out_cm:.6f} V")

    # Implement an absolute zero safeguard for perfect common-mode rejection scenarios to avoid division by zero exceptions.
    if v_out_cm == 0:
        v_out_cm = 0.000001

    # Calculate overall Common-Mode Rejection Ratio (CMRR).
    cmrr_db = 20 * np.log10((DIFFERENTIAL_GAIN * EXPECTED_V_IN) / v_out_cm)

    print(f"\nCalculated CMRR: {cmrr_db:.2f} dB")
    print("Target: > 80 dB")

    if cmrr_db > 80.0:
        print("Status: PASS")
    else:
        print("Status: FAIL")


if __name__ == "__main__":
    run_cmrr_test()