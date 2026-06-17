import serial
import time
import numpy as np
from collections import deque
from scipy.signal import butter, lfilter, lfilter_zi

# Algorithmic Test Configuration
PORT = 'COM3'
BAUD = 115200
FS = 250
HPF_CUTOFF = 0.3
EVENT_THRESHOLD_RMS = 0.04
TEST_DURATION = 32  # Duration specified to successfully capture three complete 10-second physiological cycles.


def run_dsp_test():
    try:
        ser = serial.Serial(PORT, BAUD, timeout=0.1)
        print(f"Connected to {PORT}.")
    except Exception as e:
        print(f"Hardware Error: {e}")
        return

    # Initialize the primary Digital Signal Processing (DSP) pipeline components identical to the background service.
    b, a = butter(2, HPF_CUTOFF, btype='highpass', fs=FS)
    filter_state = None
    rms_buffer = deque([0.0] * FS, maxlen=FS)

    is_recording = False
    contractions_detected = 0
    post_event_counter = 0

    input("\nPress the RESET button on your Arduino Due, then immediately press ENTER here...")
    print(f"\nAnalyzing DSP logic for {TEST_DURATION} seconds. Waiting for contractions...", flush=True)

    start_time = time.time()
    last_print = start_time
    ser.reset_input_buffer()

    while (time.time() - start_time) < TEST_DURATION:
        current_time = time.time()

        if current_time - last_print >= 2.0:
            elapsed = int(current_time - start_time)
            print(f"Time elapsed: {elapsed}s | Contractions found so far: {contractions_detected}", flush=True)
            last_print = current_time

        while ser.in_waiting > 0:
            line = ser.readline().decode('utf-8', errors='ignore').strip()
            if line:
                try:
                    val = float(line)

                    # 1. Apply High-Pass Butterworth Filter
                    if filter_state is None:
                        filter_state = lfilter_zi(b, a) * val

                    filtered_array, filter_state = lfilter(b, a, [val], zi=filter_state)

                    # 2. Compute Root Mean Square (RMS) Integration
                    rms_buffer.append(filtered_array[0])
                    current_rms = np.sqrt(np.mean(np.square(list(rms_buffer))))

                    # 3. Evaluate Event Threshold Conditions
                    if not is_recording:
                        if current_rms >= EVENT_THRESHOLD_RMS:
                            is_recording = True
                            contractions_detected += 1
                            timestamp = current_time - start_time
                            print(
                                f"\n>>> [EVENT {contractions_detected} OPENED] at {timestamp:.2f}s | Peak RMS: {current_rms:.4f}",
                                flush=True)
                    else:
                        if current_rms < EVENT_THRESHOLD_RMS:
                            post_event_counter += 1
                            if post_event_counter >= (FS * 2):  # Enforce a 2-second refractory period post-event.
                                is_recording = False
                                post_event_counter = 0
                                timestamp = current_time - start_time
                                print(f"<<< [EVENT {contractions_detected} CLOSED] at {timestamp:.2f}s", flush=True)
                        else:
                            post_event_counter = 0

                except ValueError:
                    continue

    ser.close()

    print("\n" + "=" * 40)
    print("TEST 4.3 RESULTS")
    print("=" * 40)

    print(f"Target Contractions: 3")
    print(f"Detected Contractions: {contractions_detected}")

    if contractions_detected == 3:
        print("Status: PASS (Algorithm correctly isolated the fast-wave bursts)")
    else:
        print("Status: FAIL (Algorithm threshold needs tuning or signal scaling is off)")
        print("Note: If it detected 0, lower the EVENT_THRESHOLD_RMS. If it detected too many, raise it.")


if __name__ == "__main__":
    run_dsp_test()