import timeit
from test_stream import protocols, compressions

setup = """
from pyacq.core.stream  import OutputStream, InputStream
import numpy as np
import time

nb_channel = 16
chunksize = {chunksize}
ring_size = chunksize*20
nloop = {nloop}
stream_spec = dict(protocol = {protocol}, interface = '127.0.0.1', port = '*',
                    transfertmode = {transfertmode}, streamtype = 'analogsignal',
                    dtype = 'float32', shape = (-1, nb_channel), compression ={compression},
                    scale = None, offset = None, units = '', copy={copy},
                    # for sharedarray
                    sharedarray_shape = ( ring_size, nb_channel), timeaxis = 0,
                    ring_buffer_method = 'double',
                        )
outstream = OutputStream()
outstream.configure(**stream_spec)
time.sleep(.5)
instream = InputStream()
instream.connect(outstream)

arr = np.random.rand(chunksize, nb_channel).astype(stream_spec['dtype'])
def start_loop(outstream, instream):
    index = 0
    for i in range(nloop):
        index += chunksize
        outstream.send(index, arr)
        index2, arr2 = instream.recv()
"""
    
stmt = """
start_loop(outstream, instream)
outstream.close()
instream.close()
"""

    
for chunksize, nloop in [(2**10, 10), (2**14, 1), (2**16, 10)]:
    print('#'*5)
    for protocol in protocols:            
        for compression in compressions:
            for copy in ('True ', 'False'):
                setup2 = setup.format(compression=repr(compression), protocol=repr(protocol), transfertmode="'plaindata'",
                            chunksize=chunksize, nloop=nloop, copy=repr(copy))
                t = timeit.timeit(stmt, setup=setup2, number=1)
                print(chunksize, nloop, 'plaindata  ', protocol.ljust(6), compression.ljust(13), 'copy =', copy, 'time = %0.05f' % t, 's.', 'speed', nloop*chunksize*16*4/t/1e6, 'MB/s')
    
    setup2 = setup.format(compression="''", protocol="'tcp'", transfertmode="'sharedarray'",
                chunksize=chunksize, nloop=nloop, copy="'False'")
    t = timeit.timeit(stmt, setup=setup2, number=1)
    print(chunksize, nloop, 'sharedarray', 'time =', t, 's.', 'speed', nloop*chunksize*16*4/t/1e6, 'MB/s')
