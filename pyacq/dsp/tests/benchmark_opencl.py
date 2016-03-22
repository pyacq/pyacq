"""
Some benchmark to compare CPU with numpy solution and home made OpenCL implementation.
"""
import numpy as np
import pyopencl
import scipy.signal
import time

import pyqtgraph as pg

from pyacq.dsp.sosfilter import  HAVE_PYOPENCL, sosfilter_engines


def compare(chunksize,n_section, nb_channel):
    nloop = 10
    f1, f2 = 50., 150.
    sample_rate = 1000.
    

    dtype = 'float32'
    data = np.random.randn(nloop*chunksize, nb_channel).astype('float32')
    coefficients = scipy.signal.iirfilter(n_section, [f1/sample_rate*2, f2/sample_rate*2],
                btype = 'bandpass', ftype = 'butter', output = 'sos')
    print(coefficients.shape)

    if HAVE_PYOPENCL:
        engines = ['scipy', 'opencl', 'opencl2', 'opencl3']
        #~ engines = ['scipy', 'opencl3']
    else:
        engines = ['scipy']
    
    times = []
    for engine in engines:
        print(engine)
        EngineClass = sosfilter_engines[engine]
        filter_engine = EngineClass(coefficients, nb_channel, dtype, chunksize)
        
        t1 = time.perf_counter()
        for i in range(nloop):
            chunk = data[i*chunksize:(i+1)*chunksize,:]
            filter_engine.compute_one_chunk(chunk)
        t2 = time.perf_counter()
        
        times.append(t2-t1)
    
    order = np.argsort(times)
    print([('{} {:.3f}s'.format(engines[i], times[i])) for i in order ])
    
        

def benchmark_sosfilter():
    ap = pg.mkQApp()
    
    ctx = pyopencl.create_some_context()
    print(ctx)
    
    #~ chunksizes = [256,1024,2048]
    #~ chunksizes = [2048]
    chunksizes = [64]
    #~ n_sections = [2,8,16,24]
    n_sections = [4]
    nb_channels = [1,10, 50,100, 200]
    #~ nb_channels = [10, 50, 100]
    #~ chunksizes = [1024]
    #~ n_sections = [4]
    #~ nb_channels = [100]

    
    for chunksize in chunksizes:
        for n_section in n_sections:
            for nb_channel in nb_channels:
                print('*'*20)
                print('chunksize', chunksize, 'n_section', n_section, 'nb_channel', nb_channel)
                compare(chunksize,n_section, nb_channel)
                

    
    
    
    
if __name__ == '__main__':
    benchmark_sosfilter()
