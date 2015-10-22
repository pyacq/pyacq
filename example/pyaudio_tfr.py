"""
Simple demonstration of streaming data from a PyAudio device to a QOscilloscope
viewer.

Both device and viewer nodes are created locally without a manager.
"""

from pyacq.devices.audio_pyaudio import PyAudio
from pyacq.viewers import QTimeFreq
from pyacq.core import create_manager
import pyqtgraph as pg


# Start Qt application
app = pg.mkQApp()


# Create a manager to spawn worker process to record and process audio
man = create_manager()
ng = man.create_nodegroup()


# Create PyAudio device node in remote process
dev = ng.create_node('PyAudio')

# Configure PyAudio device with a single (default) input channel.
default_input = dev.default_input_device()
dev.configure(nb_channel=1, sample_rate=44100., input_device_index=default_input,
              format='int16', chunksize=1024)
dev.output.configure(protocol='tcp', interface='127.0.0.1', transfertmode='plaindata')
dev.initialize()


# We are only recording a single audio channel, so we create one extra 
# nodegroup for processing TFR. For multi-channel signals, create more
# nodegroups.
workers = [man.create_nodegroup()]


# Create a viewer in the local application, using the remote process for
# frequency analysis
viewer = QTimeFreq()
viewer.configure(with_user_dialog=True, nodegroup_friends=workers)
viewer.input.connect(dev.output)
viewer.initialize()
viewer.show()

viewer.params['refresh_interval'] = 100
viewer.params['timefreq', 'f_start'] = 50
viewer.params['timefreq', 'f_stop'] = 5000
viewer.params['timefreq', 'deltafreq'] = 500
viewer.by_channel_params['Signal0', 'clim'] = 2500


# Start both nodes
dev.start()
viewer.start()


if __name__ == '__main__':
    import sys
    if sys.flags.interactive == 0:
        app.exec_()
