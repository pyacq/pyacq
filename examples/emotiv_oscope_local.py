"""
Simple demonstration of streaming EEG data from an Emotiv device to a QOscilloscope
viewer, for linux case.

Both device and viewer nodes are created locally without a manager.
"""

from pyacq.devices.eeg_emotiv import Emotiv
from pyacq.viewers import QOscilloscope
import pyqtgraph as pg
import os


# Start Qt application
app = pg.mkQApp()

# Create Emotiv device node
dev = Emotiv(name='Emotiv0')

# Emotiv device on linux - could be hidraw1 / hidraw2 / .. 
device_handle = '/dev/hidraw3'

# Configure Emotiv device with three outputs : signal, impedances and gyro
dev.configure(device_handle=device_handle)
dev.outputs['signals'].configure(
    protocol='tcp', interface='127.0.0.1', transfermode='plaindata',)
dev.outputs['impedances'].configure(
    protocol='tcp', interface='127.0.0.1', transfermode='plaindata',)
dev.outputs['gyro'].configure(
    protocol='tcp', interface='127.0.0.1', transfermode='plaindata',)

dev.initialize()

# Create an oscilloscope to display signal data.
viewer_signal = QOscilloscope()
viewer_signal.configure(with_user_dialog = True)
# Connect signal stream to oscilloscope
viewer_signal.input.connect(dev.outputs['signals'])
viewer_signal.initialize()
viewer_signal.show()

viewer_signal.params['mode'] = 'scan'
viewer_signal.params['xsize'] = 5
viewer_signal.auto_gain_and_offset(mode = 2)
viewer_signal.params['ylim_min'] = 8000
viewer_signal.params['ylim_max'] = 9000

# Create an oscilloscope to display gyro data.
viewer_gyro = QOscilloscope()
viewer_gyro.configure(with_user_dialog = True)
# Connect signal stream to oscilloscope
viewer_gyro.input.connect(dev.outputs['gyro'])
viewer_gyro.initialize()
viewer_gyro.show()

# Start both nodes
dev.start()
viewer_signal.start()
viewer_gyro.start()

if __name__ == '__main__':
    import sys
    if sys.flags.interactive == 0:
        app.exec_()
