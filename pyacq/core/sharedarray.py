import numpy as np
import sys, random, string, tempfile, mmap


# TODO
# On POSIX system it can optionally the shm_open way to avoid mmap.

class SharedMem:
    """Class to create a shared memory buffer.
    
    This class uses mmap so that unrelated processes (not forked) can share it.
    
    Parameters
    ----------
    size : int
        Buffer size in bytes.
    shm_id : str or None
        The id of an existing SharedMem to open. If None, then a new shared
        memory file is created.
        On linux this is the filename, on Windows this is the tagname.
    
    """
    def __init__(self, nbytes, shm_id=None):
        self.nbytes = nbytes
        self.mmap_size = (self.nbytes // mmap.PAGESIZE + 1) * mmap.PAGESIZE
        self.shm_id = shm_id
        
        if sys.platform.startswith('win'):
            if shm_id is None:
                self.shm_id = u'pyacq_SharedMem_'+''.join(random.SystemRandom().choice(string.ascii_uppercase + string.digits) for _ in range(128))
                self.mmap = mmap.mmap(-1, self.nbytes, self.shm_id, access=mmap.ACCESS_WRITE)
            else:
                self.mmap = mmap.mmap(-1, self.nbytes, self.shm_id, access=mmap.ACCESS_READ)
        else:
            if shm_id is None:
                self._tmpFile = tempfile.NamedTemporaryFile(prefix=u'pyacq_SharedMem_')
                self._tmpFile.write(b'\x00' * self.nbytes)
                self._tmpFile.flush()  # I do not anderstand but this is needed....
                self.shm_id = self._tmpFile.name
                self.mmap = mmap.mmap(self._tmpFile.fileno(), self.nbytes, mmap.MAP_SHARED, mmap.PROT_WRITE)
            else:
                self._tmpFile = open(self.shm_id, 'rb')
                self.mmap = mmap.mmap(self._tmpFile.fileno(), self.nbytes, mmap.MAP_SHARED, mmap.PROT_READ)
                
    def close(self):
        """Close this buffer.
        """
        self.mmap.close()
        if not sys.platform.startswith('win') and hasattr(self, '_tmpFile'):
            self._tmpFile.close()
    
    def to_dict(self):
        """Return a dict that can be serialized and sent to other processes to
        access this buffer.
        """
        return {'nbytes': self.nbytes, 'shm_id': self.shm_id}
    
    def to_numpy(self, offset, dtype, shape, strides):
        """Return a numpy array pointing to part (or all) of this buffer.
        """
        return np.ndarray(buffer=self.mmap, shape=shape,
                          strides=strides, offset=offset, dtype=dtype)        
        




class SharedArray:
    """Class to create shared memory that can be viewed as a `numpy.ndarray`.
    
    This class uses mmap so that unrelated processes (not forked) can share it.
    
    The parameters of the array may be serialized and passed to other processes
    using `to_dict()`::
    
        orig_array = SharedArray(shape, dtype)
        spec = pickle.dumps(orig_array.to_dict())
        shared_array = SharedArray(**pickle.loads(spec))
    
    
    Parameters
    ----------
    shape : tuple
        The shape of the array.
    dtype : str or list
        The dtype of the array (as understood by `numpy.dtype()`).
    shm_id : str or None
        The id of an existing SharedMem to open. If None, then a new shared
        memory file is created.
        On linux this is the filename, on Windows this is the tagname.
    
    """
    def __init__(self, shape=(1,), dtype='float64', shm_id=None):
        self.shape = shape
        self.dtype = np.dtype(dtype)
        nbytes = np.prod(shape)*self.dtype.itemsize
        self.shmem = SharedMem(nbytes, shm_id)
    
    def to_dict(self):
        return {'shape': self.shape, 'dtype': self.dtype, 'shm_id': self.shmem.shm_id}
    
    def to_numpy(self):
        return np.frombuffer(self.shmem.mmap, dtype=self.dtype).reshape(self.shape)

