# -*- coding: utf-8 -*-

import multiprocessing as mp
import numpy as np
import ctypes

class SharedArray:
    """
    This create a numpy shared array that can pass to subprocess.
    
    Usage:
    
    sa = SharedArray((200, 20), dtype = np.float64)
    and inside subprocess
    a = sa.to_numpy_array()
    a[30:185, 3] = 0.
    
    """
    def __init__(self, shape, dtype):
        self.dtype = np.dtype(dtype)
        self.shape = shape
        self.mp_array = mp.Array(ctypes.c_byte, np.prod(self.shape)*self.dtype.itemsize)

    def to_numpy_array(self):
        return np.frombuffer(self.mp_array.get_obj(), dtype = self.dtype).reshape(self.shape)