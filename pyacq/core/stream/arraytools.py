import numpy as np


def axis_order_copy(data, out=None):
    """Copy *data* such that the result is contiguous, but preserves the axis order
    in memory.
    
    If *out* is provided, then write the copy into that array instead creating
    a new one. *out* must be an array of the same dtype and size, with ndim=1.
    """
    # transpose to natural order
    order = np.argsort(np.abs(data.strides))[::-1]    
    data = data.transpose(order)
    # reverse axes if needed
    ind = tuple((slice(None, None, -1) if data.strides[i] < 0 else slice(None) for i in range(data.ndim)))
    data = data[ind]
    
    if out is None:
        # now copy
        data = data.copy()
    else:
        assert out.dtype == data.dtype
        assert out.size == data.size
        assert out.ndim == 1
        out[:] = data.reshape(data.size)
        data = out
    # unreverse axes
    data = data[ind]
    # and untranspose
    data = data.transpose(np.argsort(order))
    return data


def is_contiguous(data):
    """Return True if *data* occupies a contiguous block of memory.
    
    Note this is _not_ the same as asking whether an array is C-contiguous
    or F-contiguous because it does not care about the axis order or 
    direction.
    """
    order = np.argsort(np.abs(data.strides))[::-1]
    strides = np.array(data.strides)[order]
    shape = np.array(data.shape)[order]
    
    if abs(strides[-1]) != data.itemsize:
        return False
    for i in range(data.ndim-1):
        if abs(strides[i]) != abs(strides[i+1] * shape[i+1]):
            return False
        
    return True


def decompose_array(data):
    """Return the components needed to efficiently serialize and unserialize
    an array:
    
    1. A contiguous data buffer that can be sent via socket
    2. An offset into the buffer
    3. Strides into the buffer
    
    Shape and dtype can be pulled directly from the array. 
    
    If the input array is discontiguous, it will be copied using axis_order_copy().
    """
    if not is_contiguous(data):
        # socket.send requires a contiguous buffer
        data = axis_order_copy(data)
        
    buf = normalized_array(data)
    offset = data.__array_interface__['data'][0] - buf.__array_interface__['data'][0]
    
    return buf, offset, data.strides


def normalized_array(data):
    """Return *data* with axis order and direction normalized.
    
    This will only transpose and reverse axes; the array data is not copied.
    If *data* is contiguous in memory, then this returns a C-contiguous array.
    """
    order = np.argsort(np.abs(data.strides))[::-1]    
    data = data.transpose(order)
    # reverse axes if needed
    ind = tuple((slice(None, None, -1) if data.strides[i] < 0 else slice(None) for i in range(data.ndim)))
    return data[ind]


