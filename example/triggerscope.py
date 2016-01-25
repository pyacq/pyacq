"""
Simple demonstration of streaming data from a simulated electrode array
to a QOscilloscope viewer.

Both device and viewer nodes are created locally without a manager.
"""

from pyacq.devices import FakeSpikeSource
from pyacq.viewers import QTriggeredOscilloscope
import pyqtgraph as pg


# Start Qt application
app = pg.mkQApp()


source = FakeSpikeSource(nb_channel=1)
source.output.params['nb_channel'] = 1

# Create a triggered oscilloscope to display data.
viewer = QTriggeredOscilloscope()
viewer.configure(with_user_dialog = True)

# Connect audio stream to oscilloscope
viewer.input.connect(source.output)

viewer.initialize()
viewer.show()
#viewer.params['decimation_method'] = 'min_max'
#viewer.by_channel_params['Signal0', 'gain'] = 0.001

viewer.trigger.params['threshold'] = -3e-3
viewer.trigger.params['debounce_mode'] = 'after-stable'
viewer.trigger.params['front'] = '+'
viewer.trigger.params['debounce_time'] = 0.001
viewer.triggeraccumulator.params['stack_size'] = 3
viewer.triggeraccumulator.params['left_sweep'] = -.01
viewer.triggeraccumulator.params['right_sweep'] = .01
viewer.by_channel_params['Signal0', 'gain'] = 1000


# Start both nodes
source.start()
viewer.start()


if __name__ == '__main__':
    import sys
    if sys.flags.interactive == 0:
        app.exec_()
