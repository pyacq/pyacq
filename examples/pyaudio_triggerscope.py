"""
Simple demonstration of streaming data from a PyAudio device to a QOscilloscope
viewer.

Both device and viewer nodes are created locally without a manager.
"""

from pyacq.devices.audio_pyaudio import PyAudio
from pyacq.viewers import QTriggeredOscilloscope
import pyqtgraph as pg


# Start Qt application
app = pg.mkQApp()


# Create PyAudio device node
dev = PyAudio()

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
dev.output.configure(protocol='tcp', interface='127.0.0.1', transfermode='plaindata')
dev.initialize()


# Create a triggered oscilloscope to display data.
viewer = QTriggeredOscilloscope()
viewer.configure(with_user_dialog = True)

# Connect audio stream to oscilloscope
viewer.input.connect(dev.output)

viewer.initialize()
viewer.show()
#viewer.params['decimation_method'] = 'min_max'
#viewer.by_channel_params['Signal0', 'gain'] = 0.001

viewer.trigger.params['threshold'] = 1.
viewer.trigger.params['debounce_mode'] = 'after-stable'
viewer.trigger.params['front'] = '+'
viewer.trigger.params['debounce_time'] = 0.1
viewer.triggeraccumulator.params['stack_size'] = 3
viewer.triggeraccumulator.params['left_sweep'] = -.2
viewer.triggeraccumulator.params['right_sweep'] = .5


# Start both nodes
dev.start()
viewer.start()


if __name__ == '__main__':
    import sys
    if sys.flags.interactive == 0:
        app.exec_()
