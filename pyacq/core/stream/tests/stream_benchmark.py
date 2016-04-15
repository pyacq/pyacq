import time
import numpy as np
import cProfile
import sys

from test_stream import protocols, compressions
from pyacq.core.stream  import OutputStream, InputStream


def benchmark_stream(protocol, transfertmode, compression, chunksize, nb_channels=16, nloop=10, profile=False):
    ring_size = chunksize*20
    stream_spec = dict(protocol=protocol, interface='127.0.0.1', port='*',
                       transfertmode=transfertmode, streamtype = 'analogsignal',
                       dtype='float32', shape=(-1, nb_channels), compression=compression,
                       scale=None, offset=None, units='',
                       # for sharedarray
                       sharedarray_shape = ( ring_size, nb_channels), timeaxis = 0,
                       ring_buffer_method = 'double',
                  )
    outstream = OutputStream()
    outstream.configure(**stream_spec)
    time.sleep(.5)
    instream = InputStream()
    instream.connect(outstream)

    arr = np.random.rand(chunksize, nb_channels).astype(stream_spec['dtype'])
    
    perf = []
    prof = cProfile.Profile()
    for i in range(nloop):
        start = time.perf_counter()
        if profile:
            prof.enable()
        outstream.send(arr)
        index2, arr2 = instream.recv()
        if profile:
            prof.disable()
        perf.append(time.perf_counter() - start)
    if profile:
        prof.print_stats('cumulative')
    
    outstream.close()
    instream.close()
    
    dt = np.min(perf)
    print(chunksize, nloop, transfertmode, protocol.ljust(6), compression.ljust(13), 'time = %0.02f ms' % (dt*1000), 'speed = ', chunksize*nb_channels*4*1e-6/dt, 'MB/s')
    
    return dt



if len(sys.argv) > 1 and sys.argv[1] == 'profile':
    benchmark_stream(protocol='inproc', transfertmode='plaindata', 
                    compression='', chunksize=100000, nb_channels=16,
                    profile=True, nloop=100)
    

else:
    nb_channels = 16
    for chunksize in [2**10, 2**14, 2**16]:
        print('#'*5)
        for compression in compressions:
            for protocol in protocols:
                benchmark_stream(protocol=protocol, transfertmode='plaindata', 
                                compression=compression,
                                chunksize=chunksize, nb_channels=nb_channels)

        benchmark_stream(protocol='tcp', transfertmode='sharedarray', compression='',
                        chunksize=chunksize, nb_channels=nb_channels)
