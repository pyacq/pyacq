import time
import numpy as np
from test_stream import protocols, compressions

from pyacq.core.stream  import OutputStream, InputStream


def benchmark_stream(protocol, transfertmode, compression, chunksize, nb_channels=16, nloop=10):
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
    for i in range(nloop):
        start = time.perf_counter()
        outstream.send(arr)
        index2, arr2 = instream.recv()
        perf.append(time.perf_counter() - start)

    
    outstream.close()
    instream.close()
    
    dt = np.min(perf)
    print(chunksize, nloop, transfertmode, protocol.ljust(6), compression.ljust(13), 'time = %0.02f ms' % (dt*1000), 'speed = ', chunksize*nb_channels*4*1e-6/dt, 'MB/s')
    
    return dt


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
