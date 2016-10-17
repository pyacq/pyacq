"""
Some benchmark to compare CPU with numpy solution and home made OpenCL implementation.

For each filter there is several implementation that do not have
the same bench depending on the hardware.
On nvidia, the opencl seems to be the faster.
On intel GPU, opencl3 seems to be the faster.
In any case for low, nb_channel and nb_section scipy (CPU) implementation 
is the fastest.



"""
import numpy as np
import pyopencl
import scipy.signal
import time

import pyqtgraph as pg

from pyacq.dsp.sosfilter import  HAVE_PYOPENCL, sosfilter_engines
from pyacq.dsp.overlapfiltfilt import  HAVE_PYOPENCL, sosfiltfilt_engines


def compare(chunksize,n_section, nb_channel, engines_classes, engines, **extra_kargs):
    nloop = 20
    f1, f2 = 50., 150.
    sample_rate = 1000.
    
    dtype = 'float32'
    data = np.random.randn(nloop*chunksize, nb_channel).astype('float32')
    coefficients = scipy.signal.iirfilter(n_section, [f1/sample_rate*2, f2/sample_rate*2],
                btype = 'bandpass', ftype = 'butter', output = 'sos')
    #~ print(coefficients.shape)

    times = []
    for engine in engines:
        print(engine)
        EngineClass = engines_classes[engine]
        filter_engine = EngineClass(coefficients, nb_channel, dtype, chunksize,  **extra_kargs)
        
        #~ try:
        if 1:
            t1 = time.perf_counter()
            for i in range(nloop):
                pos = (i+1)*chunksize
                chunk = data[pos-chunksize:pos,:]
                filter_engine.compute_one_chunk(pos, chunk)
            t2 = time.perf_counter()
            
            times.append(t2-t1)
        #~ except:
            #~ times.append(np.inf)
    
    order = np.argsort(times)
    #~ order = np.arange(len(engines))
    print([('{} {:.3f}s'.format(engines[i], times[i])) for i in order ])
    
        

def benchmark_sosfilter():
    ctx = pyopencl.create_some_context()
    print(ctx)
    
    chunksizes = [256,1024,2048]
    #~ chunksizes = [2048]
    #~ chunksizes = [64]
    #~ n_sections = [2,8,16,24]
    n_sections = [8, 24]
    #~ n_sections = [24]
    #~ nb_channels = [1,10, 50,100, 200]
    nb_channels = [10, 50, 100]
    #~ nb_channels = [10, 50, 100, 500]
    #~ nb_channels = [10, 50, 100]
    #~ chunksizes = [1024]
    #~ n_sections = [4]
    #~ nb_channels = [100]
    
    if HAVE_PYOPENCL:
        engines = ['scipy', 'opencl', 'opencl2', 'opencl3']
        #~ engines = ['scipy', 'opencl3']
    else:
        engines = ['scipy']

    for chunksize in chunksizes:
        for n_section in n_sections:
            for nb_channel in nb_channels:
                print('*'*20)
                print('chunksize', chunksize, 'n_section', n_section, 'nb_channel', nb_channel)
                compare(chunksize,n_section, nb_channel, sosfilter_engines, engines)
                

def benchmark_overlapfiltfilt():
    ctx = pyopencl.create_some_context()
    print(ctx)
    
    #~ chunksizes = [256,1024,2048]
    chunksizes = [2048]
    #~ chunksizes = [64]
    #~ n_sections = [2,8,16,24]
    n_sections = [8, 24]
    #~ n_sections = [24]
    #~ nb_channels = [1,10, 50,100, 200]
    nb_channels = [10, 50, 100]
    #~ nb_channels = [10, 50, 100, 500]
    #~ nb_channels = [10, 50, 100]
    #~ chunksizes = [1024]
    #~ n_sections = [4]
    #~ nb_channels = [100]
    
    if HAVE_PYOPENCL:
        engines = ['scipy', 'opencl', 'opencl3']
    else:
        engines = ['scipy']

    extra_kargs = {'overlapsize' : 64}
    
    for chunksize in chunksizes:
        for n_section in n_sections:
            for nb_channel in nb_channels:
                print('*'*20)
                print('chunksize', chunksize, 'n_section', n_section, 'nb_channel', nb_channel)
                compare(chunksize,n_section, nb_channel, sosfiltfilt_engines, engines, **extra_kargs)
    
    
    
    
if __name__ == '__main__':
    benchmark_sosfilter()
    #~ benchmark_overlapfiltfilt()

