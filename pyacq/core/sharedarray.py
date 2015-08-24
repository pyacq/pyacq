import numpy as np
import atexit
import sys, random, string, tempfile, mmap


# TODO
# On POSIX system it can optionally the shm_open way to avoid mmap.

class SharedArray:
    """
    Class to create a shared memory that can be veiw as a numpy.narray
    
    The approach use mmap file based to do this.
    So unrelated process (not forked) can share it.
    
    You can serialize the dict that descibe this sharedmem with to_dict.
    
    
    
    Parameters
    ----------
    shape: tuple
        The shape of the array.
    
    dtype: str or list
        The dtype numpy like style.
    
    shm_id: str
        The id of the SharedMem If None then create it. If not None 
        On linux this is the fileno() on Window this is the tagname.
    
    """
    def __init__(self, shape = (1,), dtype = 'float64', shm_id =  None):
        self.shape = shape
        self.dtype = np.dtype(dtype)
        self.nbytes = np.prod(shape)*self.dtype.itemsize
        self.length = (self.nbytes//mmap.PAGESIZE+1) * mmap.PAGESIZE
        self.shm_id = shm_id
        
        if sys.platform.startswith('win'):
            if shm_id is None:
                self.shm_id = u'pyacq_SharedMem_'+''.join(random.SystemRandom().choice(string.ascii_uppercase + string.digits) for _ in range(128))
            self.mmap = mmap.mmap(-1, self.nbytes, self.shm_id, access = mmap.ACCESS_WRITE)
        else:
            if shm_id is None:
                self._tmpFile = tempfile.NamedTemporaryFile(prefix='pyacq_SharedMem_')
                self._tmpFile.write(b'\x00' * self.length)
                self._tmpFile.flush() # I do not anderstand but this is needed....
                self.shm_id = self._tmpFile.fileno()
            self.mmap = mmap.mmap(self.shm_id, self.nbytes, mmap.MAP_SHARED)#, mmap.PROT_WRITE)
        atexit.register(self.close)
    
    def close(self):
        self.mmap.close()
        if not sys.platform.startswith('win') and hasattr(self, '_tmpFile'):
            self._tmpFile.close()
    
    def to_dict(self):
        return { 'shape' : self.shape, 'dtype' : self.dtype, 'shm_id' : self.shm_id }
    
    def to_numpy(self):
        return np.frombuffer(self.mmap, dtype = self.dtype).reshape(self.shape)

