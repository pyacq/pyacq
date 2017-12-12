"""
Simple demonstration of streaming data from a NIDAQmx device to a QOscilloscope
viewer.
Both device and viewer nodes are created locally without a manager.
"""

from pyacq.devices.ni_daqmx import NIDAQmx
from pyacq.viewers import QOscilloscope
import pyqtgraph as pg
from pyqtgraph.Qt import QtCore, QtGui

import numpy as np

# Start Qt application
app = pg.mkQApp()


# Configure DAQ device with two analog input channels.
sr = 40e3
aichannels = ['Dev1/ai0', 'Dev1/ai1', 'Dev1/ai2', 'Dev1/ai3',]
aochannels =  ['Dev1/ao0', 'Dev1/ao1']

#create 2 output short signals than will be played every seconds
times =np.arange(0,0.5, 1./sr)
freq, ampl = 5., 2.5
sig0 = np.sin(2*np.pi*freq*times).astype('float64')*ampl
sig1 = np.random.randn(sig0.size).astype('float64')
sigs = np.concatenate((sig0[None, :], sig1[None, :]), axis=0)
sigs[:, -1] = 0 #last sample is back 0


# Create NI DAQmx device node
dev = NIDAQmx()

dev.configure(sample_rate=sr,
    chunksize=1000,
    aichannels=aichannels, 
    aimodes = {'Dev1/ai0':'rse', 'Dev1/ai1': 'rse'},
    airanges= (-5., 5.),#for all channels
    magnitude_mode='float32_volt',
    aochannels=aochannels,
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

# Start both nodes
dev.start()
viewer.start()


def periodic_play_ao():
    print('periodic_play_ao')
    dev.play_ao(aochannels, sigs)

timer = QtCore.QTimer(interval=1000, singleShot=False)
timer.timeout.connect(periodic_play_ao)
timer.start()



if __name__ == '__main__':
    import sys
    if sys.flags.interactive == 0:
        app.exec_()
