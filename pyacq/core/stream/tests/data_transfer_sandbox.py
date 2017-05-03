from copy import copy
import time
import numpy as np
import zmq
import ctypes

ctx = zmq.Context()

sock1 = ctx.socket(zmq.PAIR)
sock2 = ctx.socket(zmq.PAIR)

sock1.bind('tcp://127.0.0.1:*')
sock2.connect(sock1.getsockopt(zmq.LAST_ENDPOINT))


def full_test(data):
    """Measure time required to send *data* across socket.
    
    Attempts to minimize the number of copies made while preserving memory
    layout:
    
    * Use copy=False in socket.send()
    * Create ndarray directly from socket.recv() buffer
    * If data is contiguous (but with any axis order/direction), send as-is
    * If data is truly discontiguous in memory, then make a copy that preserves
      axis order/direction.
    """
    
    # test copy functions
    assert np.all(axis_order_copy(data) == data)
    assert np.all(exact_copy(data) == data)
    print("    contiguous data:", is_contiguous(data))
    
    # test sending with and without socket.send(copy=False)
    data_orig = data
    for copy in (True, False):
        
        print("    send with copy=%s" % copy)
        perf = []
        # measure min of 10 trials
        for i in range(10):
            data = exact_copy(data_orig)
            start = time.perf_counter()

            shape = data.shape
            dtype = data.dtype
            base, offset, strides = decompose_array(data)
            
            sock1.send(base, copy=copy)  # 20% performance boost for copy=False
            
            # 20% performance boost for using np.frombuffer
            d = np.ndarray(buffer=sock2.recv(), shape=shape,
                        strides=strides, offset=offset, dtype=dtype)
            
            perf.append(time.perf_counter() - start)
        
        dt = np.min(perf)
        print("        =>  %0.2f ms  \t  %0.2f MB/s" % (dt * 1000, (d.size*d.itemsize) * 1e-6 / dt))

        # Check array copied correctly
        assert d.dtype == data_orig.dtype
        assert d.shape == data_orig.shape
        assert np.all(d == data_orig)
        
        # Check axis order in memory is preserved
        assert d.strides == strides


def fast_test(data):
    """Test fastest possible data transfer (with no extra features) to benchmark
    against the full test.
    """
    assert data.flags['C_CONTIGUOUS']
    for copy in (True, False):
        print("    send with copy=%s" % copy)
        perf = []
        # measure min of 10 trials
        for i in range(10):
            start = time.perf_counter()
            sock1.send(data, copy=copy)  # 20% performance boost for copy=False
            d = np.ndarray(buffer=sock2.recv(), shape=data.shape, dtype=data.dtype)
            perf.append(time.perf_counter() - start)
        
        dt = np.min(perf)
        print("        => %0.2f ms\t%0.2f MB/s" % (dt * 1000, (d.size*d.itemsize) * 1e-6 / dt))

        # Check array copied correctly
        assert d.dtype == data.dtype
        assert d.shape == data.shape
        assert np.all(d == data)


def exact_copy(data):
    """Make an identical copy of *data*, including memory layout and discontiguities.
    """
    base = data.base
    if base is None:
        return data.copy()
    
    if hasattr(base, 'copy'):
        base = base.copy()
    else:
        base = copy(base)
    
    offset = array_offset(data)
    return np.ndarray(buffer=base.data, shape=data.shape, strides=data.strides,
                      offset=offset, dtype=data.dtype)


def array_offset(data):
    """Measure byte offset of array origin relative to its underlying memory buffer.
    """
    if data.base is None:
        base = data
    else:
        base = data.base
        if not isinstance(base, np.ndarray):
            base = np.frombuffer(base, dtype=np.ubyte)
    base = normalized_array(base)
    return data.__array_interface__['data'][0] - base.__array_interface__['data'][0]
        

def axis_order_copy(data):
    """Copy *data* such that the result is contiguous, but preserves the axis order
    in memory.
    """
    # transpose to natural order
    order = np.argsort(np.abs(data.strides))[::-1]    
    data = data.transpose(order)
    # reverse axes if needed
    ind = tuple((slice(None, None, -1) if data.strides[i] < 0 else slice(None) for i in range(data.ndim)))
    data = data[ind]
    # now copy
    data = data.copy()
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
    
    If *data* is contiguous in memory, then this retorns a C-contiguous array.
    """
    order = np.argsort(np.abs(data.strides))[::-1]    
    data = data.transpose(order)
    # reverse axes if needed
    ind = tuple((slice(None, None, -1) if data.strides[i] < 0 else slice(None) for i in range(data.ndim)))
    return data[ind]



def run_tests(data):
    full_test(data)
    print("transposed")
    full_test(data.T)
    print("reversed")
    full_test(data[::-1])
    print("reversed, transposed")
    full_test(data[::-1].T)
    print("reversed, transposed, offset")
    full_test(data[1:-1][::-1].T)

size = np.array([100, 200, 300])
data = np.random.normal(size=size)  # 48MB

print("Fast send:")
print("==========")
fast_test(data)

print("Contiguous")
print("==========")
run_tests(data)


data = np.random.normal(size=size * [2, 1, 1])[::2]  # 48MB
print("Non-contiguous")
print("==============")
run_tests(data)


data = np.frombuffer(b'\0'*(data.size*data.itemsize), dtype=data.dtype).reshape(data.shape)
print("From buffer")
print("===========")
run_tests(data)


data = np.frombuffer(b'\0'*(2 * data.size*data.itemsize), dtype=data.dtype).reshape((200, 200, 300))[::2]
print("From buffer, discontiguous")
print("==========================")
run_tests(data)


