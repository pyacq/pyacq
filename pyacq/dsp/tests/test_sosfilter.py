# -*- coding: utf-8 -*-
# Copyright (c) 2016, French National Center for Scientific Research (CNRS)
# Distributed under the (new) BSD License. See LICENSE for more info.

import pytest
import time
import numpy as np
import pyqtgraph as pg

from pyacq import create_manager, NumpyDeviceBuffer
from pyacq.dsp.sosfilter import SosFilter, HAVE_PYOPENCL, sosfilter_engines
from pyacq.viewers.qoscilloscope import QOscilloscope

from pyqtgraph.Qt import QtCore, QtGui
import scipy.signal

import time

nb_channel = 10
sample_rate =1000.
#~ chunksize = 500
chunksize = 10
nloop = 200

length = int(chunksize*nloop)
times = np.arange(length)/sample_rate
buffer = np.random.rand(length, nb_channel) *.3
f1, f2, speed = 20., 60., .05
freqs = (np.sin(np.pi*2*speed*times)+1)/2 * (f2-f1) + f1
phases = np.cumsum(freqs/sample_rate)*2*np.pi
ampl = np.abs(np.sin(np.pi*2*speed*8*times))*.8
buffer += (np.sin(phases)*ampl)[:, None]

buffer = buffer.astype('float32')


def do_filtertest(engine):
    stream_spec = dict(protocol='tcp', interface='127.0.0.1', transfermode='sharedmem',
                            double=True, dtype = 'float32',buffer_size=2048*50, shape=(-1,nb_channel))
    
    app = pg.mkQApp()
    
                            
    dev = NumpyDeviceBuffer()
    dev.configure(nb_channel=nb_channel, sample_interval=1./sample_rate, chunksize=chunksize,
                    buffer=buffer)
    dev.output.configure( **stream_spec)
    dev.initialize()
    
    
    f1, f2 = 40., 60.
    
    coefficients = scipy.signal.iirfilter(7, [f1/sample_rate*2, f2/sample_rate*2],
                btype = 'bandpass', ftype = 'butter', output = 'sos')
    
    filter = SosFilter()
    filter.configure(coefficients = coefficients, engine=engine, chunksize=chunksize)
    filter.input.connect(dev.output)
    filter.output.configure(**stream_spec)
    filter.initialize()
    
    viewer = QOscilloscope()
    viewer.configure(with_user_dialog=True)
    viewer.input.connect(filter.output)
    viewer.initialize()
    viewer.show()

    viewer2 = QOscilloscope()
    viewer2.configure(with_user_dialog=True)
    viewer2.input.connect(dev.output)
    viewer2.initialize()
    viewer2.show()
    
    viewer2.start()
    viewer.start()
    filter.start()
    dev.start()
    
    
    def terminate():
        dev.stop()
        filter.stop()
        viewer.stop()
        viewer2.stop()
        app.quit()
    
    # start for a while
    timer = QtCore.QTimer(singleShot=True, interval=3000)
    timer.timeout.connect(terminate)
    timer.start()
    
    app.exec_()

def test_sosfilter():
    do_filtertest('scipy')

@pytest.mark.skipif(not HAVE_PYOPENCL, reason='no pyopencl')
def test_openclsosfilter():
    do_filtertest('opencl')
    do_filtertest('opencl2')
    do_filtertest('opencl3')



def compare_online_offline_engines():
    
    if HAVE_PYOPENCL:
        engines = ['scipy', 'opencl', 'opencl2', 'opencl3']
        #~ engines = ['opencl3']
    else:
        engines = ['scipy']
    
    
    dtype = 'float32'
    
    coefficients = scipy.signal.iirfilter(7, [f1/sample_rate*2, f2/sample_rate*2],
                btype = 'bandpass', ftype = 'butter', output = 'sos')
    
    offline_arr =  scipy.signal.sosfilt(coefficients.astype('float32'), buffer.astype('float32'), axis=0, zi=None)
    offline_arr = offline_arr.astype('float32')
    
    for engine in engines:
        print(engine)
        EngineClass = sosfilter_engines[engine]
        filter_engine = EngineClass(coefficients, nb_channel, dtype, chunksize)
        print(filter_engine)
        online_arr = np.zeros_like(offline_arr)
        
        t1 = time.clock()
        for i in range(nloop):
            #~ print(i)
            chunk = buffer[i*chunksize:(i+1)*chunksize,:]
            chunk_filtered = filter_engine.compute_one_chunk(None, chunk)
            #~ print(chunk_filtered.shape)
            #~ print(online_arr[i*chunksize:(i+1)*chunksize,:])
            online_arr[i*chunksize:(i+1)*chunksize,:] = chunk_filtered
            #~ print(online_arr[i*chunksize:(i+1)*chunksize,:])
        t2 = time.clock()

        residual = np.abs((online_arr.astype('float64')-offline_arr.astype('float64'))/np.mean(np.abs(offline_arr.astype('float64'))))
        print(np.max(residual))
        print(t2-t1)
        #~ assert np.max(residual)<1e-4, 'online differt from offline'
    
        from matplotlib import pyplot
        fig, ax = pyplot.subplots()
        ax.plot(offline_arr[:, 2], color = 'g')
        ax.plot(online_arr[:, 2], color = 'r', ls='--')
        fig, ax = pyplot.subplots()
        for c in range(nb_channel):
            ax.plot(residual[:, c], color = 'k')
    pyplot.show()
        
    
    
    

if __name__ == '__main__':
    #~ test_sosfilter()
    test_openclsosfilter()
    
    #~ compare_online_offline_engines()

 
