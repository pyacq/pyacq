# -*- coding: utf-8 -*-
# Copyright (c) 2016, French National Center for Scientific Research (CNRS)
# Distributed under the (new) BSD License. See LICENSE for more info.

import pytest

from pyacq import create_manager
from pyacq.viewers.qoscilloscope import QOscilloscope
from pyacq.devices import NumpyDeviceBuffer
from pyacq.rec import RawRecorder
import numpy as np

from pyqtgraph.Qt import QtCore, QtGui
import pyqtgraph as pg

import os
import shutil
import datetime



def test_RawRecorder():
    
    man = create_manager(auto_close_at_exit=False)
    ng0 = man.create_nodegroup()
    ng1 = man.create_nodegroup()
    
    app = pg.mkQApp()
    
    #~ transfermode
    
    
    sample_rates = [100., 1000., 10000.]
    nb_channels = [16, 32, 1]
    dtypes = ['float32', 'int16', 'float64']
    chunksizes = [25, 250, 2000]
    
    devices = []
    for i in  range(3):
        sample_rate, nb_channel = sample_rates[i], nb_channels[i]
        chunksize, dtype = chunksizes[i],  dtypes[i]
        
        length = int(sample_rate*3)
        length = length - length%chunksize
        t = np.arange(length)/sample_rate
        buffer = np.random.rand(length, nb_channel)*.3
        buffer += np.sin(2*np.pi*1.2*t)[:,None]*.5
        buffer = buffer.astype(dtype)

        dev = ng0.create_node('NumpyDeviceBuffer', name='dev{}'.format(i))
        #~ dev = NumpyDeviceBuffer()
        dev.configure(nb_channel=nb_channel, sample_interval=1./sample_rate, chunksize=chunksize, buffer=buffer)
        dev.output.configure(protocol='tcp', interface='127.0.0.1', transfermode='plaindata')
        dev.initialize()
        devices.append(dev)


    dirname = './test_rec'
    if os.path.exists(dirname):
        shutil.rmtree(dirname)
    
    rec = RawRecorder()
    #~ rec = ng1.create_node('RawRecorder')
    rec.configure(streams=[dev.output for dev in devices], autoconnect=True, dirname=dirname)
    rec.initialize()
    
    rec.add_annotations(yep='abc', yop=12.5, yip=1)

    def terminate():
        
        for dev in devices:
            dev.stop()
            dev.close()
        rec.stop()
        rec.close()
        
        app.quit()
    

    rec.start()
    for dev in devices:
        dev.start()
    
    # start for a while
    timer = QtCore.QTimer(singleShot=True, interval=2000)
    timer.timeout.connect(terminate)
    timer.start()
    
    app.exec_()

    man.close()


if __name__ == '__main__':
    test_RawRecorder()

