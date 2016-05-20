import numpy as np

from .sharedarray import SharedMem, SharedArray


class RingBuffer:
    """Class that collects data as it arrives from an InputStream and writes it
    into a single- or double-ring buffer.
    
    This allows the user to request the concatenated history of data
    received by the stream, up to a predefined length. Double ring buffers
    allow faster, copyless reads at the expense of doubled write time and memory
    footprint.
    """
    def __init__(self, shape, dtype, double=True, shmem=None, fill=None, axisorder=None):
        self.double = double
        self.shape = shape
        # order of axes as written in memory. This does not affect the shape of the 
        # buffer as seen by the user, but can be used to make sure a specific axis
        # is contiguous in memory.
        if axisorder is None:
            axisorder = np.arange(len(shape))
        self.axisorder = np.array(axisorder)
        
        shape = (shape[0] * (2 if double else 1),) + shape[1:]
        nativeshape = np.array(shape)[self.axisorder]
        
        # initialize int buffers with 0 and float buffers with nan
        if fill is None:
            fill = 0 if np.dtype(dtype).kind in 'ui' else np.nan
        self._filler = fill
        
        if shmem is None:
            self.buffer = np.empty(nativeshape, dtype=dtype).transpose(np.argsort(axisorder))
            self.buffer[:] = self._filler
            self._indexes = np.zeros((2,), dtype='int64')
            self._shmem = None
            self.shm_id = None
        else:
            size = np.product(shape) * np.dtype(dtype).itemsize + 16
            if shmem is True:
                # create new shared memory buffer
                self._shmem = SharedMem(nbytes=size)
            else:
                self._shmem = SharedMem(nbytes=size, shm_id=shmem)
            buf = self._shmem.to_numpy(offset=16, dtype=dtype, shape=nativeshape)
            self.buffer = buf.transpose(np.argsort(axisorder))
            self._indexes = self._shmem.to_numpy(offset=0, dtype='int64', shape=(2,))
            self.shm_id = self._shmem.shm_id
        
        self.dtype = self.buffer.dtype
        
        if shmem in (None, True):
            # Index of last writable sample + 1. This value is used to determine which
            # buffer indices map to which data indices (where buffer indices wrap
            # around to 0, but data indices always increase as data arrives).
            self._set_write_index(0)
            # Index of last written sample + 1. This is used to determine how much of
            # the buffer is *valid* for reading.
            self._set_read_index(0)
        
        # Note: read_index and write_index are defined independently to avoid
        # race condifions with processes reading and writing from the same
        # shared memory simultaneously. When new data arrives:
        #   1. write_index is increased to indicate that the buffer has advanced
        #      and some old data is no longer valid
        #   2. new data is written over the old buffer data
        #   3. read_index is increased to indicate that the new data is now
        #      readable

        #
        #              write_index-bsize     break_index      read_index       write_index
        #              |                     |                |                |
        #    ..........[.....................|...............][...............]
        #                                    |
        #              [           readable area             ][ writable area ]
        #                                    |
        #                                    |  [........]           read without copy
        #                        [........]  |                       read without copy
        #                               [....|......]                read with copy
        # 
        
    def index(self):
        return self._read_index

    def first_index(self):
        return self._read_index - self.shape[0]

    @property
    def _write_index(self):
        return self._indexes[1]

    @property
    def _read_index(self):
        return self._indexes[0]

    def _set_write_index(self, i):
        # what kind of protection do we need here?
        self._indexes[1] = i

    def _set_read_index(self, i):
        # what kind of protection do we need here?
        self._indexes[0] = i

    def new_chunk(self, data, index=None):
        dsize = data.shape[0]
        bsize = self.shape[0]
        if dsize > bsize:
            raise ValueError("Data chunk size %d is too large for ring "
                            "buffer of size %d." % (dsize, bsize))
        if data.dtype != self.dtype:
            raise TypeError("Data has incorrect dtype %s (buffer requires %s)" %
                            (data.dtype, self.dtype))
        
        # by default, index advances by the size of the chunk
        if index is None:
            index = self._write_index + dsize
        
        assert dsize <= index - self._write_index, ("Data size is %d, but index "
                                                    "only advanced by %d." % 
                                                    (dsize, index-self._write_index)) 

        revert_inds = [self._read_index, self._write_index]
        try:
            # advance write index. This immediately prevents other processes from
            # accessing memory that is about to be overwritten.
            self._set_write_index(index)
            
            # decide if any skipped data needs to be filled in
            fill_start = max(self._read_index, self._write_index - bsize)
            fill_stop = self._write_index - dsize
            
            if fill_stop > fill_start:
                # data was skipped; fill in missing regions with 0 or nan.
                self._write(fill_start, fill_stop, self._filler)
                revert_inds[1] = fill_stop
                
            self._write(self._write_index - dsize, self._write_index, data)
                
            self._set_read_index(index)
        except:
            # If there is a failure writing data, revert read/write pointers
            self._set_read_index(revert_inds[0])
            self._set_write_index(revert_inds[1])
            raise

    def _write(self, start, stop, value):
        # get starting index
        bsize = self.shape[0]
        dsize = stop - start
        i = start % bsize
        
        if self.double:
            self.buffer[i:i+dsize] = value
            i += bsize
        
        if i + dsize <= self.buffer.shape[0]:
            self.buffer[i:i+dsize] = value
        else:
            n = self.buffer.shape[0]-i
            self.buffer[i:] = value[:n]
            self.buffer[:dsize-n] = value[n:]
        
    def __getitem__(self, item):
        if isinstance(item, tuple):
            first = item[0]
            rest = (slice(None),) + item[1:]
        else:
            first = item
            rest = None
        
        if isinstance(first, (int, np.integer)):
            start = self._interpret_index(first)
            stop = start + 1
            data = self.get_data(start, stop)[0]
            if rest is not None:
                data = data[rest[1:]]
        elif isinstance(first, slice):
            start, stop, step = self._interpret_index(first)
            data = self.get_data(start, stop)[::step]
            if rest is not None:
                data = data[rest]
        else:
            raise TypeError("Invalid index type %s" % type(first))
        
        return data

    def get_data(self, start, stop, copy=False, join=True):
        """Return a segment of the ring buffer.
        
        Parameters
        ----------
        start : int
            The starting index of the segment to return.
        stop : int
            The stop index of the segment to return (the sample at this index
            will not be included in the returned data)
        copy : bool
            If True, then a copy of the data is returned to ensure that modifying
            the data will not affect the ring buffer. If False, then a reference to
            the buffer will be returned if possible. Default is False.
        join : bool
            If True, then a single contiguous array is returned for the entire
            requested segment. If False, then two separate arrays are returned
            for the beginning and end of the requested segment. This can be
            used to avoid an unnecessary copy when the buffer has double=False
            and the caller does not require a contiguous array.
        """
        first, last = self.first_index(), self.index()
        if start < first or stop > last:
            raise IndexError("Requested segment (%d, %d) is out of bounds for ring buffer. "
                             "Current bounds are (%d, %d)." % (start, stop, first, last))
        
        bsize = self.shape[0]
        copied = False
        
        if self.double:
            # This do not work when get_data(-10, 50) meaning stop=50 length=60 (start=stop-length)
            # this is util at the beging to get larger buffer than already possible
            #start_ind = start % bsize
            #stop_ind = start_ind + (stop - start)
            
            # I prefer this which equivalent but work with start<0:
            stop_ind = stop%bsize + bsize
            start_ind = stop_ind - (stop - start)
            
            data = self.buffer[start_ind:stop_ind]
        else:
            break_index = self._write_index - (self._write_index % bsize)
            if (start < break_index) == (stop <= break_index):
                start_ind = start % bsize
                stop_ind = start_ind + (stop - start)
                data = self.buffer[start_ind:stop_ind]
            else:
                # need to reconstruct from two pieces
                newshape = np.array((stop-start,) + self.shape[1:])[self.axisorder]
                a = self.buffer[start%bsize:]
                b = self.buffer[:stop%bsize]
                if join is False:
                    if copy is True:
                        return (a.copy(), b.copy())
                    else:
                        return (a, b)
                else:
                    data = np.empty(newshape, self.buffer.dtype).transpose(np.argsort(self.axisorder))
                    data[:break_index-start] = a
                    data[break_index-start:] = b
                    copied = True
        
        if copy and not copied:
            data = data.copy()
            
        if join:
            return data
        else:
            empty = np.empty((0,) + data.shape[1:], dtype=data.dtype)
            return data, empty

    def _interpret_index(self, index):
        """Return normalized index, accounting for negative and None values.
        Also check that the index is readable.
        
        Slices are returned such that start,stop are swapped and shifted -1 if
        the step is negative. This makes it possible to collect the result in
        the forward direction and handle the step later.
        """
        start_index = self._write_index - self.shape[0]
        if isinstance(index, (int, np.integer)):
            if index < 0:
                index += self._read_index
            if index >= self._read_index or index < start_index:
                raise IndexError("Index %d is out of bounds for ring buffer [%d:%d]" %
                                 (index, start_index, self._read_index))
            return index
        elif isinstance(index, slice):
            start, stop, step = index.start, index.stop, index.step
            
            # Handle None and negative steps
            if step is None:
                step = 1
            if step < 0:
                start, stop = stop, start
                
            # Interpret None and negative indices
            if start is None:
                start = start_index
            else:
                if start < 0:
                    start += self._read_index
                if step < 0:
                    start += 1 
                
            if stop is None:
                stop = self._read_index
            else:
                if stop < 0:
                    stop += self._read_index
                if step < 0:
                    stop += 1
                
            # Bounds check.
            # Perhaps we could clip the returned data like lists/arrays do,
            # but in this case the feedback is likely to be useful to the user.
            if stop > self._read_index or stop < start_index:
                raise IndexError("Stop index %d is out of bounds for ring buffer [%d, %d]" %
                                 (stop, start_index, self._read_index))
            if start > self._read_index or start < start_index:
                raise IndexError("Start index %d is out of bounds for ring buffer [%d, %d]" %
                                 (start, start_index, self._read_index))
            return start, stop, step
        else:
            raise TypeError("Invalid index %s" % index)
