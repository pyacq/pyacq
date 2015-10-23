"""
Simple demonstration of streaming data from a PyAudio device to a QOscilloscope
viewer.

Both device and viewer nodes are created locally without a manager.
"""

import pyqtgraph as pg

from pyacq.viewers import QOscilloscope
import pyacq.core.rpc as rpc

app = pg.mkQApp()


# Create PyAudio device node in remote process
dev_proc = rpc.ProcessSpawner()
dev = dev_proc.client._import('pyacq.devices.audio_pyaudio').PyAudio()

# Print a list of available input devices (but ultimately we will just use the 
# default device).
default_input = dev.default_input_device()
print("\nAvaliable devices:")
for device in dev.list_device_specs():
    index = device['index']
    star = "*" if index == default_input else " "
    print("  %s %d: %s" % (star, index, device['name']))

# Configure PyAudio device with a single (default) input channel.
dev.configure(nb_channel=1, sample_rate=44100., input_device_index=default_input,
              format='int16', chunksize=1024)
dev.output.configure(protocol='tcp', interface='127.0.0.1', transfertmode='plaindata')
dev.initialize()


# Create an oscilloscope to display data.
viewer = QOscilloscope()
viewer.configure(with_user_dialog = True)

# Connect audio stream to oscilloscope
viewer.input.connect(dev.output)

viewer.initialize()
viewer.show()
viewer.params['decimation_method'] = 'min_max'
viewer.by_channel_params['Signal0', 'gain'] = 0.001

# Start both nodes
dev.start()
viewer.start()

app.exec_()