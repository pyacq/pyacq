"""
Simple demonstration of streaming data from a PyAudio device to a QOscilloscope
viewer.
Both device and viewer nodes are created locally without a manager.
"""

from pyacq.devices.ni_daqmx import NIDAQmx
from pyacq.viewers import QOscilloscope
import pyqtgraph as pg


# Start Qt application
app = pg.mkQApp()


# Create NI DAQmx device node
dev = NIDAQmx()


# Configure DAQ device with two analog input channels.
sr = 40e3
dev.configure(aisamplerate=sr, aichannels=['Dev1/ai0', 'Dev1/ai1', 'Dev1/ai3', 'Dev1/ai4',], 
    aimodes = {'Dev1/ai0':'rse', 'Dev1/ai1': 'rse'},
    airanges= (-5., 5.),#for all channels
    chunksize=100,
    magnitude_mode='float32_volt',
    )


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
viewer.params['ylim_max'] = 5.
viewer.params['ylim_min'] = -5.
viewer.params['mode'] = 'scan'

#viewer.by_channel_params['Signal0', 'gain'] = 0.001

# Start both nodes
dev.start()
viewer.start()


if __name__ == '__main__':
    import sys
    if sys.flags.interactive == 0:
        app.exec_()
