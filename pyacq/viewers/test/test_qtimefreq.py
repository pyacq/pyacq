# -*- coding: utf-8 -*-
# Copyright (c) 2016, French National Center for Scientific Research (CNRS)
# Distributed under the (new) BSD License. See LICENSE for more info.

import logging

import numpy as np
import pyqtgraph as pg
import pytest
from pyqtgraph.Qt import QtCore

from pyacq import create_manager
from pyacq.viewers.qtimefreq import QTimeFreq, HAVE_SCIPY

logger = logging.getLogger()

#~ nb_channel = 8
nb_channel = 2
sample_rate = 1000.
chunksize = 50

#~ nb_channel = 32
#~ sample_rate = 20000
#~ chunksize = 100

# some moving sinus
length = int(sample_rate*20)
times = np.arange(length)/sample_rate
buffer = np.random.rand(length, nb_channel)
f1, f2, speed = 20., 60., .05
freqs = (np.sin(np.pi*2*speed*times)+1)/2 * (f2-f1) + f1
phases = np.cumsum(freqs/sample_rate)*2*np.pi
ampl = np.abs(np.sin(np.pi*2*speed*8*times))*.8
buffer += (np.sin(phases)*ampl)[:,None]
buffer = buffer.astype('float32')


def lauch_qtimefreq(transfermode, axisorder, localworker):
    # TODO test with other axis order
    
    #~ man = create_manager(auto_close_at_exit = True)
    man = create_manager(auto_close_at_exit=False)
    ng = man.create_nodegroup()
    
    app = pg.mkQApp()
    
    dev = ng.create_node('NumpyDeviceBuffer')
    dev.configure(nb_channel=nb_channel, sample_interval=1./sample_rate, chunksize=chunksize, buffer=buffer)
    if transfermode=='sharedmem':
        buffer_size = int(62.*sample_rate)
    else:
        buffer_size = 0
    dev.output.configure(protocol='tcp', interface='127.0.0.1', transfermode=transfermode,
                    buffer_size=buffer_size, double=True)
    dev.initialize()
    
    if localworker:
        nodegroup_friends = None
    else:
        nodegroup_friends = [man.create_nodegroup() for _ in range(4)]
    
    viewer = QTimeFreq()
    viewer.configure(with_user_dialog=True, nodegroup_friends=nodegroup_friends)
    viewer.input.connect(dev.output)
    viewer.initialize()
    viewer.show()
    
    viewer.params['nb_column'] = 1
    viewer.params['refresh_interval'] = 1000
    
    
    def terminate():
        viewer.stop()
        dev.stop()
        viewer.close()
        dev.close()
        app.quit()
    
    dev.start()

    viewer.start()
    
    # start for a while
    timer = QtCore.QTimer(singleShot=True, interval=3000)
    timer.timeout.connect(terminate)
    # timer.start()
    
    app.exec_()
    
    man.close()
    
# TODO test with other axis order

@pytest.mark.skipif(not HAVE_SCIPY, reason='no HAVE_SCIPY')
def test_qtimefreq_local_worker():
    lauch_qtimefreq('plaindata', [0,1], True)
    #lauch_qtimefreq('plaindata', [1,0], True)
    # lauch_qtimefreq('sharedmem', [0,1], True)
    #lauch_qtimefreq('sharedmem', [1,0], True)

@pytest.mark.skipif(not HAVE_SCIPY, reason='no HAVE_SCIPY')
def test_qtimefreq_distributed_worker():
    lauch_qtimefreq('plaindata', [0,1], False)
    #lauch_qtimefreq('plaindata', [1,0], False)
    lauch_qtimefreq('sharedmem', [0,1], False)
    #lauch_qtimefreq('sharedmem', [1,0], False)




if __name__ == '__main__':
    test_qtimefreq_local_worker()
    # test_qtimefreq_distributed_worker()


