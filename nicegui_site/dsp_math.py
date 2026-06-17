import numpy as np
from scipy.signal import welch, hilbert, find_peaks

FS = 250
BAND_FWL = (0.34, 1.0)
BAND_FWH = (1.0, 3.0)


def extract_features(df_event, previous_end_time, ibi_history):
    voltages = df_event['voltage'].values
    timestamps = df_event['timestamp'].values
    N = len(voltages)

    if N < 50:  # Discard transient artifact events shorter than 0.2 seconds.
        return None

    v_centered = voltages - np.mean(voltages)
    rms = float(np.sqrt(np.mean(np.square(v_centered))))
    max_amp = float(np.max(np.abs(v_centered)))

    t_start = float(timestamps[0])
    burst_duration = float(timestamps[-1] - t_start)

    ibi = None
    if previous_end_time is not None:
        ibi = float(t_start - previous_end_time)
        ibi_history.append(ibi)

    freqs, psd = welch(v_centered, fs=FS, nperseg=min(N, FS * 10))
    dominant_freq = float(freqs[np.argmax(psd)])

    # Compute High-Frequency Fast Wave (FWH) power density.
    idx_fwh = np.logical_and(freqs >= BAND_FWH[0], freqs <= BAND_FWH[1])
    power_fwh = float(np.trapezoid(psd[idx_fwh], freqs[idx_fwh]))

    # Compute Low-Frequency Fast Wave (FWL) power density.
    idx_fwl = np.logical_and(freqs >= BAND_FWL[0], freqs <= BAND_FWL[1])
    power_fwl = float(np.trapezoid(psd[idx_fwl], freqs[idx_fwl]))

    return {
        'event_id': str(df_event['event_id'].iloc[0]),
        'timestamp_start': t_start,
        'rms_v': rms,
        'max_amplitude_v': max_amp,
        'burst_duration_sec': burst_duration,
        'ibi_sec': ibi,
        'dominant_freq_hz': dominant_freq,
        'power_fwh': power_fwh,
        'power_fwl': power_fwl  # Included for comprehensive spectral analysis payload.
    }