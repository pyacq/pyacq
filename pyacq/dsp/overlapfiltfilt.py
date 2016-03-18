from pyqtgraph.Qt import QtCore
import pyqtgraph as pg
import weakref
import numpy as np

from ..core import (Node, register_node_type, ThreadPollInput)
from ..core.stream import SharedArraySender

import distutils.version
try:
    import scipy.signal
    HAVE_SCIPY = True
    # scpy.signal.sosfilt was introduced in scipy 0.16
    assert distutils.version.LooseVersion(scipy.__version__)>'0.16'
except ImportError:
    HAVE_SCIPY = False

try:
    import pyopencl
    mf = pyopencl.mem_flags
    HAVE_PYOPENCL = True
except ImportError:
    HAVE_PYOPENCL = False

from .sosfilter import sos_filter_kernel

class OverlapFiltfiltThread(ThreadPollInput):
    def __init__(self, input_stream, output_stream, chunksize, overlapsize, timeout = 200, parent = None):
        ThreadPollInput.__init__(self, input_stream, timeout = timeout, parent = parent)
        self.output_stream = weakref.ref(output_stream)
        self.chunksize = chunksize
        self.overlapsize = overlapsize
        
        
        #TODO when branch stream-performence is done
        self.forward_buffer = ArrayRingBuffer()
    
    def process_data(self, pos, data):
        if data is None:
            #sharred_array case
            data =  self.input_stream().get_array_slice(pos, None)
        assert data.shape[0] == self.chunksize, 'Filtfilt need fixed chunksize'
        
        # Forward 
        forward_data_filtered, self.zi = scipy.signal.sosfilt(self.coefficients, data, zi=self.zi, axis=0)
        self.forward_buffer.new_chunk(forward_data_filtered, pos)
        
        # Backward 
        buf = self.forward_buffer[pos-self.chunksize-self.overlap:pos, ::-1]
        backward_filtered = scipy.signal.sosfilt(self.coefficients, buf, zi=None, axis=0)
        backward_filtered = backward_filtered[::-1]
        
        #send
        self.output_stream().send(pos, backward_filtered[:chunksize])
        
    def set_params(self, coefficients, nb_channel, dtype):
        self.coefficients = coefficients
        self.n_sections = coefficients.shape[0]
        self.zi = np.zeros((self.n_sections, 2, nb_channel), dtype= dtype)

class OpenCL_OverlapFiltfiltThread(ThreadPollInput):
    def __init__(self, input_stream, output_stream, chunksize, overlapsize, timeout = 200, parent = None):
        ThreadPollInput.__init__(self, input_stream, timeout = timeout, parent = parent)
        self.output_stream = weakref.ref(output_stream)
        self.chunksize = chunksize
        self.overlapsize = overlapsize
        self.chunksize2 = self.chunksize + self.overlapsize
        
        #TODO when branch stream-performence is done
        self.forward_buffer = ArrayRingBuffer()

        self.ctx = pyopencl.create_some_context()
        #TODO : add arguments gpu_platform_index/gpu_device_index
        #self.devices =  [pyopencl.get_platforms()[self.gpu_platform_index].get_devices()[self.gpu_device_index] ]
        #self.ctx = pyopencl.Context(self.devices)
        #~ print(self.ctx)
        self.queue = pyopencl.CommandQueue(self.ctx)
        prg = pyopencl.Program(self.ctx, sos_filter_kernel)
        self.opencl_prg = prg.build(options='-cl-mad-enable')
        
    
    def process_data(self, pos, data):
        if data is None:
            #sharred_array case
            data =  self.input_stream().get_array_slice(pos, None)
        assert data.shape[0] == self.chunksize, 'Filtfilt need fixed chunksize'
        assert data.dtype==self.dtype
        
        # Forward 
        data1 = data.transpose()
        if not data1.flags['C_CONTIGUOUS']:
            data1 = data1.copy()
        pyopencl.enqueue_copy(self.queue,  self.input1_cl, data)

        kern_call = self.opencl_prg.sos_filter
        kern_call.set_args(np.uint32(self.chunksize), np.int32(self.n_section), np.int32(1),
                                self.input1_cl, self.output1_cl, self.coefficients_cl, self.zi1_cl)
        event = pyopencl.enqueue_nd_range_kernel(self.queue,kern_call, self.global_size, self.local_size,)
        event.wait()
        pyopencl.enqueue_copy(self.queue,  self.output, self.output_cl)
        forward_data_filtered = self.output.transpose()
        self.forward_buffer.new_chunk(forward_data_filtered, pos)
        
        # Backward 
        data2 = self.forward_buffer[pos-self.chunksize-self.overlap:pos, ::-1]
        data2 = data2.transpose()
        self.zi2[:]=0
        if not data2.flags['C_CONTIGUOUS']:
            data2 = data2.copy()
        pyopencl.enqueue_copy(self.queue,  self.input2_cl, data2)
        pyopencl.enqueue_copy(self.queue,  self.zi2_cl, self.zi2)
        
        kern_call = self.opencl_prg.sos_filter
        kern_call.set_args(np.uint32(self.chunksize2), np.int32(self.n_section), np.int32(-1),
                                self.input2_cl, self.output2_cl, self.coefficients_cl, self.zi2_cl)
        event = pyopencl.enqueue_nd_range_kernel(self.queue,kern_call, self.global_size, self.local_size)
        event.wait()
        
        pyopencl.enqueue_copy(self.queue,  self.output2, self.output2_cl)
        forward_data_filtered = self.output2.transpose()
        
        self.output_stream().send(pos, backward_filtered[:chunksize])


    def set_params(self, coefficients, nb_channel, dtype):
        self.dtype = np.dtype(dtype)
        assert self.dtype == np.dtype('float32') 
        self.nb_channel = nb_channel
        
        self.coefficients = coefficients.astype(self.dtype)
        if self.coefficients.ndim==2: #(nb_section, 6) to (nb_channel, nb_section, 6)
            self.coefficients = np.tile(self.coefficients[None,:,:], (nb_channel, 1,1))
        if not self.coefficients.flags['C_CONTIGUOUS']:
            self.coefficients = self.coefficients.copy()
        self.n_section = self.coefficients.shape[1]
        assert self.coefficients.shape[0]==self.nb_channel, 'wrong coefficients.shape'
        assert self.coefficients.shape[2]==6, 'wrong coefficients.shape'
        
        #host arrays
        self.zi1 = np.zeros((nb_channel, self.n_section, 2), dtype= self.dtype)
        self.output1 = np.zeros((self.nb_channel, self.chunksize), dtype= self.dtype)
        self.output2 = np.zeros((self.nb_channel, self.chunksize2), dtype= self.dtype)
        
        #GPU buffers
        self.coefficients_cl = pyopencl.Buffer(self.ctx, mf.READ_ONLY | mf.COPY_HOST_PTR, hostbuf=self.coefficients)
        self.zi1_cl = pyopencl.Buffer(self.ctx, mf.READ_WRITE | mf.COPY_HOST_PTR, hostbuf=self.zi1)
        self.zi2_cl = pyopencl.Buffer(self.ctx, mf.READ_WRITE | mf.COPY_HOST_PTR, hostbuf=self.zi2)
        self.input1_cl = pyopencl.Buffer(self.ctx, mf.READ_WRITE, size=self.output1.nbytes)
        self.output1_cl = pyopencl.Buffer(self.ctx, mf.READ_WRITE, size=self.output1.nbytes)
        self.input2_cl = pyopencl.Buffer(self.ctx, mf.READ_WRITE, size=self.output2.nbytes)
        self.output2_cl = pyopencl.Buffer(self.ctx, mf.READ_WRITE, size=self.output2.nbytes)

        
        #nb works
        self.global_size = (self.nb_channel, self.n_section)
        self.local_size = (1, self.n_section, )


class OverlapFiltfilt(Node,  QtCore.QObject):
    """
    Node for filtering with forward-backward method (filtfilt).
    This use sliding overlap technics.
    
    The chunksize and the overlapsize are important for the accuracy of filtering.
    You need to study them carfully, otherwise the result should be the same as a
    real filtfilt ona long term signal. You must check the residual between real offline filtfitl
    and this online OverlapFiltfilt.
    Note that the chunksize have a strong effect on low frequency.
    
    This uses Second Order (sos) coeeficient.
    It internally use scipy.signal.sosfilt which is available only on scipy >0.16
    
    
    The chunksize need to be fixed.
    For overlapsize there are 2 cases:
      1-  overlapsize<chunksize/2 : natural case. each chunk partailly overlap. 
            The overlap are on sides, the central part come from one chunk.
      2 - overlapsize>chunksize/2: chunk are fully averlapping. There is no central part.
    In the 2 cases, for each arrival of new chunk at [-chunksize:], 
    the computed chunk at [-(chunksize+overlapsize):-overlapsize] is released.


    The coefficients.shape must be (n_section, 6).
    
    If pyopencl is avaible you can do SosFilter.configure(engine='opencl')
    In that cases the coefficients.shape can also be (n_channel, n_section, 6)
    this help for having different filter on each channels.
    
    The opencl engine prefer inernally (channel, sample) ordered.
    In case not a copy is done. So the input ordering do impact performences.
    
    
    
    """
    
    _input_specs = {'signals' : dict(streamtype = 'signals')}
    _output_specs = {'signals' : dict(streamtype = 'signals')}
    
    def __init__(self, parent = None, **kargs):
        QtCore.QObject.__init__(self, parent)
        Node.__init__(self, **kargs)
        assert HAVE_SCIPY, "SosFilter need scipy>0.16"
    
    def _configure(self, chunksize=1024, overlapsize=512, coefficients = None, engine='numpy'):
        """
        Set the coefficient of the filter.
        See http://scipy.github.io/devdocs/generated/scipy.signal.sosfilt.html for details.
        """
        self.chunksize = chunksize
        self.overlapsize = overlapsize
        self.engine = engine
        self.set_coefficients(coefficients)

    def after_input_connect(self, inputname):
        self.nb_channel = self.input.params['nb_channel']
        for k in ['sample_rate', 'dtype', 'nb_channel', 'shape', 'timeaxis']:
            self.output.spec[k] = self.input.params[k]
    
    def _initialize(self):
        self.thread = OverlapFiltfiltThread(self.input, self.output, self.chunksize, self.overlapsize)
        self.thread.set_params(self.coefficients, self.nb_channel, self.output.params['dtype'])


        if self.engine == 'numpy':
            self.thread = OverlapFiltfiltThread(self.input, self.output, self.chunksize, self.overlapsize)
        elif  self.engine == 'opencl':
            assert HAVE_PYOPENCL, 'need pyopencl change engine to numpy'
            assert self.chunksize is not None, 'for OpenCL engine need fixed chunksize'
            self.thread = OpenCL_OverlapFiltfiltThread(self.input, self.output, self.chunksize, self.overlapsize)
        
        self.thread.set_params(self.coefficients, self.nb_channel, self.output.params['dtype'])
        
    
    def _start(self):
        self.thread.last_pos = None
        self.thread.start()
    
    def _stop(self):
        self.thread.stop()
        self.thread.wait()
    
    def set_coefficients(self, coefficients):
        self.coefficients = coefficients
        if self.initialized():
            self.thread.set_params(self.coefficients, self.nb_channel, self.output.params['dtype'])

register_node_type(OverlapFiltfilt)