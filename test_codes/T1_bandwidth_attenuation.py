import serial
import time
import pandas as pd

# Hardware Test Configuration
PORT = 'COM3'
BAUD = 115200  # Ensure microcontroller serial baud rate configuration matches identically.
TEST_DURATION = 62  # Total test evaluation duration in seconds.


def run_hardware_test():
    try:
        ser = serial.Serial(PORT, BAUD, timeout=0.1)
        print(f"Connected to {PORT}.")
    except Exception as e:
        print(f"Could not connect to {PORT}. Error: {e}")
        return

    print("\nACTION REQUIRED:")
    input(
        "Press the RESET button on your Arduino Due, then immediately click this console and press ENTER to start recording...")

    print(f"\nRecording for {TEST_DURATION} seconds. Do not touch the hardware...", flush=True)

    data = []
    start_time = time.time()
    last_print_time = start_time

    ser.reset_input_buffer()

    while (time.time() - start_time) < TEST_DURATION:
        current_time = time.time()

        # Force standard output flush for real-time acquisition progress tracking.
        if current_time - last_print_time >= 2.0:
            elapsed = int(current_time - start_time)
            print(f"Recording progress: {elapsed} / {TEST_DURATION} seconds elapsed...", flush=True)
            last_print_time = current_time

        # Process the complete input buffer prior to executing subsequent time-check operations.
        while ser.in_waiting > 0:
            line = ser.readline().decode('utf-8', errors='ignore').strip()
            if line:
                try:
                    voltage_val = float(line)
                    simulated_time = len(data) * (1.0 / 250.0)
                    data.append((simulated_time, voltage_val))
                except ValueError:
                    continue

    ser.close()
    print("\nRecording complete. Processing data...\n", flush=True)

    df = pd.DataFrame(data, columns=['Time', 'Voltage'])

    if len(df) == 0:
        print("No data received. Check your wiring, COM port, and ensure Seeeduino is set to 500000 BAUD.")
        return

    df.to_csv('test_1_1_raw_data.csv', index=False)
    print("Raw data saved to 'test_1_1_raw_data.csv'.")

    perform_math_calculations(df)


def perform_math_calculations(df):
    print("\n" + "=" * 40)
    print("TEST 1.1 RESULTS")
    print("=" * 40)

    total_samples = len(df)
    fs_actual = total_samples / TEST_DURATION

    print("\nStep 1: Sampling Rate")
    print(f"Target: >= 250 Hz")
    print(f"Actual: {fs_actual:.2f} Hz")
    if fs_actual >= 245:
        print("Result: PASS")
    else:
        print("Result: FAIL")

    stages = [
        {"freq": "0.1 Hz", "start": 1, "end": 14},
        {"freq": "1.0 Hz", "start": 16, "end": 29},
        {"freq": "2.5 Hz", "start": 31, "end": 44},
        {"freq": "5.0 Hz", "start": 46, "end": 59}
    ]

    reference_v_out = None

    for stage in stages:
        print(f"\n--- Stage: {stage['freq']} ---")

        mask = (df['Time'] >= stage['start']) & (df['Time'] <= stage['end'])
        stage_df = df.loc[mask]

        if len(stage_df) == 0:
            print("Not enough data recorded for this stage.")
            continue

        v_max = stage_df['Voltage'].max()
        v_min = stage_df['Voltage'].min()
        v_out = v_max - v_min

        if reference_v_out is None:
            reference_v_out = v_out
            attenuation = 0.0
            print(f"Baseline Reference Voltage established at: {reference_v_out:.4f} V")
        else:
            attenuation = ((reference_v_out - v_out) / reference_v_out) * 100

        print(f"V_max: {v_max:.4f} V")
        print(f"V_min: {v_min:.4f} V")
        print(f"V_out (Peak-to-Peak): {v_out:.4f} V")
        print(f"Attenuation from Baseline: {attenuation:.2f}%")

        if attenuation <= 5.0:
            print("Status: PASS (< 5% attenuation)")
        else:
            print("Status: FAIL (> 5% attenuation)")


if __name__ == "__main__":
    run_hardware_test()