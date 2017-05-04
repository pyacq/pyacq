
from pyacq.core.stream.sharedarray import SharedArray, SharedMem
import numpy as np
import pyqtgraph.multiprocess as mp


def test_sharedmem():
    shm1 = SharedMem(nbytes=10)
    arr1 = shm1.to_numpy(offset=2, shape=8, dtype='ubyte')
    assert arr1.flags['WRITEABLE']
    
    shm2 = SharedMem(nbytes=10, shm_id=shm1.shm_id)
    arr2 = shm2.to_numpy(offset=2, shape=8, dtype='ubyte')
    assert not arr2.flags['WRITEABLE']


def test_sharedarray():    
    sa = SharedArray(shape=(10), dtype = 'int32')
    np_a = sa.to_numpy()
    np_a[:] = np.arange(10)
    
    sa2 = SharedArray(**sa.to_dict())
    np_a2 = sa.to_numpy()
    assert np_a is not np_a2
    assert np.all(np_a == np_a2)


def test_sharedarray_multiprocess():
    sa = SharedArray(shape=(10), dtype = 'int32')
    np_a = sa.to_numpy()
    np_a[:] = np.arange(10)
    
    # Start remote process, read data from shared array, then return to host
    # process.
    proc = mp.Process()
    sa_mod = proc._import('pyacq.core.stream.sharedarray')
    sa2 = sa_mod.SharedArray(**sa.to_dict())
    np_a2 = sa2.to_numpy(_returnType='value')
    proc.close()
    
    assert np.all(np_a == np_a2)
    
    
if __name__ == '__main__':
    test_sharedmem()
    test_sharedarray()
    test_sharedarray_multiprocess()
