"""
Simple demonstration of streaming data from a PyAudio device to a QOscilloscope
viewer.

Both device and viewer nodes are created locally without a manager.
"""

from pyacq.devices.nidaqmx import NIDAQmx
from pyacq.viewers import QOscilloscope
import pyqtgraph as pg


# Start Qt application
app = pg.mkQApp()


# Create NI DAQmx device node
dev = NIDAQmx()


# Configure DAQ device with two analog input channels.
dev.configure(aisamplerate=50e3, aichannels={
    'Dev1/ai0': 'NRSE',
    'Dev1/ai1': 'NRSE'
})

dev.outputs['aichannels'].configure(protocol='tcp', interface='127.0.0.1', transfertmode='plaindata')
dev.initialize()


# Create an oscilloscope to display data.
viewer = QOscilloscope()
viewer.configure(with_user_dialog = True)

# Connect audio stream to oscilloscope
viewer.input.connect(dev.output)

viewer.initialize()
viewer.show()
viewer.params['decimation_method'] = 'min_max'
#viewer.by_channel_params['Signal0', 'gain'] = 0.001

# Start both nodes
dev.start()
viewer.start()


if __name__ == '__main__':
    import sys
    if sys.flags.interactive == 0:
        app.exec_()
