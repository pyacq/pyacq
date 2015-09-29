
from pyacq.core.sharedarray import SharedArray
import numpy as np
import multiprocessing as mp



def test_sharedarray():    
    sa = SharedArray(shape = (10), dtype = 'int32')
    np_a = sa.to_numpy()
    np_a[:] = np.arange(10)
    
    sa2 = SharedArray(**sa.to_dict())
    np_a2 = sa.to_numpy()
    assert np_a is not np_a2
    assert np.all(np_a ==np_a2)


def check_sharedarray(d):
    sa2 = SharedArray(**d)
    np_a2 = sa2.to_numpy()
    assert np.all(np_a2 ==np.arange(10))


def test_sharedarray_multiprocess():
    sa = SharedArray(shape = (10), dtype = 'int32')
    np_a = sa.to_numpy()
    np_a[:] = np.arange(10)
    
    mp.set_start_method('spawn')
    proc = mp.Process(target=check_sharedarray, args=(sa.to_dict(), ))
    proc.start()
    proc.join()
    
    
if __name__ == '__main__':
    test_sharedarray()
    test_sharedarray_multiprocess()