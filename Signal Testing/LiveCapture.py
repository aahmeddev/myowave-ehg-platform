import sys
import serial
import numpy as np
import pyqtgraph as pg
from pyqtgraph.Qt import QtCore

# Configuration Parameters
PORT = 'COM3'
BAUD = 115200
FS = 250  # Sampling frequency in Hz.
WINDOW_SEC = 5  # Temporal duration of data visible on screen.
BUFFER_SIZE = FS * WINDOW_SEC

# 1. Serial Interface Initialization
try:
    # Configure non-blocking serial read with zero implicit timeout.
    ser = serial.Serial(PORT, BAUD, timeout=0.1)
    print(f"Connected to {PORT}.")
except Exception as e:
    print(f"Connection failed: {e}")
    sys.exit()

# 2. Graphical User Interface (GUI) Setup
app = pg.mkQApp("Real-Time EHG Monitor")
win = pg.GraphicsLayoutWidget(show=True, title="Live EHG Capture")
win.resize(1000, 600)

# Initialize the primary plotting area.
plot = win.addPlot(title="Infinite Real-Time Signal")
plot.setYRange(-1.0, 2.0)  # Calibrate Y-axis limits based on expected physiological voltage.
plot.showGrid(x=True, y=True)
plot.setLabel('left', 'Voltage', units='V')

# Initialize optimized plot curve for high-performance real-time rendering.
curve = plot.plot(pen=pg.mkPen('r', width=1))

# 3. Memory Buffer Allocation
data_buffer = np.zeros(BUFFER_SIZE)


# 4. Display Update Routine
def update():
    global data_buffer
    new_data_found = False

    # Flush and sequentially process all pending serial buffer data.
    while ser.in_waiting > 0:
        line_raw = ser.readline().decode('utf-8', errors='ignore').strip()
        if line_raw:
            try:
                val = float(line_raw)
                # Shift memory buffer leftward to automatically discard the oldest sample.
                data_buffer[:-1] = data_buffer[1:]
                # Append the newest sample to the termination of the buffer array.
                data_buffer[-1] = val
                new_data_found = True
            except ValueError:
                continue

    # Trigger UI redraw operations strictly upon new data acquisition to preserve computational overhead.
    if new_data_found:
        curve.setData(data_buffer)


# 5. Refresh Timer Initialization
timer = QtCore.QTimer()
timer.timeout.connect(update)
timer.start(10)  # Poll serial buffer continuously at 10-millisecond intervals.

# Execute the primary application loop.
if __name__ == '__main__':
    print("Plotting started. Close the window to exit.")
    pg.exec()
    ser.close()