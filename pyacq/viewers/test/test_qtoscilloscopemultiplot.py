# -*- coding: utf-8 -*-
# Copyright (c) 2016, French National Center for Scientific Research (CNRS)
# Distributed under the (new) BSD License. See LICENSE for more info.

import numpy as np
import pyqtgraph as pg
from pyqtgraph.Qt import QtCore

from pyacq import create_manager
from pyacq.viewers.qoscilloscopemultiplot import QOscilloscopeMultiPlot

#~ nb_channel = 32
nb_channel = 5
sample_rate = 1000.
chunksize = 100


def lauch_qoscilloscopemultiplot(transfermode, axisorder):
    
    man = create_manager(auto_close_at_exit=False)
    ng = man.create_nodegroup()
    
    app = pg.mkQApp()
    
    length = int(sample_rate*20)
    t = np.arange(length)/sample_rate
    buffer = np.random.rand(length, nb_channel)*.3
    buffer += np.sin(2*np.pi*1.2*t)[:,None]*.5
    # add offset 
    buffer += np.random.randn(nb_channel)[None, :]*50
    buffer[:, -1] = 0
    buffer = buffer.astype('float32')

    #~ dev =NumpyDeviceBuffer()
    dev = ng.create_node('NumpyDeviceBuffer')
    dev.configure(nb_channel=nb_channel, sample_interval=1./sample_rate, chunksize=chunksize, buffer=buffer)
    if transfermode== 'plaindata':
        dev.output.configure(protocol='tcp', interface='127.0.0.1', transfermode='plaindata')
    elif transfermode== 'sharedmem':
        dev.output.configure(protocol='tcp', interface='127.0.0.1', transfermode='sharedmem',
                    buffer_size=int(sample_rate*62.), axisorder=axisorder, double=True)
    dev.initialize()

    
    viewer = QOscilloscopeMultiPlot()
    viewer.configure(with_user_dialog=True)
    viewer.input.connect(dev.output)
    viewer.initialize()
    viewer.show()
    viewer.params['decimation_method'] = 'min_max'
    #~ viewer.params['scale_mode'] = 'by_channel'


    def terminate():
        viewer.stop()
        dev.stop()
        viewer.close()
        dev.close()
        app.quit()
    
    dev.start()
    viewer.start()
    
    # start for a while
    timer = QtCore.QTimer(singleShot=True, interval=2000)
    timer.timeout.connect(terminate)
    timer.start()
    
    app.exec_()

    man.close()


def test_qoscilloscopemultiplot1():
    lauch_qoscilloscopemultiplot(transfermode='sharedmem', axisorder=[0,1])

  

if __name__ == '__main__':
    test_qoscilloscopemultiplot1()
