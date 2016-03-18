from pyqtgraph.Qt import QtCore
import pyqtgraph as pg
import weakref
import numpy as np

from ..core import (Node, register_node_type, ThreadPollInput, StreamConverter)

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
    
#See
#http://scipy.github.io/devdocs/generated/scipy.signal.sosfilt.html


class SosFilterThread(ThreadPollInput):
    def __init__(self, input_stream, output_stream, timeout = 200, parent = None):
        ThreadPollInput.__init__(self, input_stream, timeout = timeout, parent = parent)
        self.output_stream = weakref.ref(output_stream)

    def process_data(self, pos, data):
        if data is None:
            #sharred_array case
            data =  self.input_stream().get_array_slice(pos, None)
        
        data_filtered, self.zi = scipy.signal.sosfilt(self.coefficients, data, zi = self.zi, axis = 0)
        self.output_stream().send(pos, data_filtered)
        
    def set_params(self, coefficients, nb_channel, dtype):
        self.coefficients = coefficients
        self.n_section = coefficients.shape[0]
        self.zi = np.zeros((self.n_section, 2, nb_channel), dtype= dtype)



class OpenCLSosFilterThread(ThreadPollInput):
    """
    Implementation of SosFilterThread using PyOpenCL.
    
    Internally each channel need to be in C_CONTINOUS (nb_channelxchunksize).
    So this is faster to use on signals that have internanly this shape.
    
    """
    def __init__(self, input_stream, output_stream, chunksize, timeout = 200, parent = None):
        ThreadPollInput.__init__(self, input_stream, timeout = timeout, parent = parent)
        self.output_stream = weakref.ref(output_stream)
        self.chunksize = chunksize
        
        self.ctx = pyopencl.create_some_context()
        #TODO : add arguments gpu_platform_index/gpu_device_index
        #self.devices =  [pyopencl.get_platforms()[self.gpu_platform_index].get_devices()[self.gpu_device_index] ]
        #self.ctx = pyopencl.Context(self.devices)
        #~ print(self.ctx)
        self.queue = pyopencl.CommandQueue(self.ctx)
        self.opencl_prg = pyopencl.Program(self.ctx, sos_filter_kernel%dict(chunksize = self.chunksize)).build(options='-cl-mad-enable')

    def process_data(self, pos, data):
        if data is None:
            #sharred_array case
            data =  self.input_stream().get_array_slice(pos, None)
        assert data.dtype==self.dtype
        
        data = data.transpose()
        if not data.flags['C_CONTIGUOUS']:
            data = data.copy()
        pyopencl.enqueue_copy(self.queue,  self.input_cl, data)

        pyopencl.enqueue_copy(self.queue,  self.zi, self.zi_cl)
        
        kern_call = self.opencl_prg.sos_filter
        kern_call.set_args(np.int32(self.n_section), np.int32(1),
                                self.input_cl, self.output_cl, self.coefficients_cl, self.zi_cl)
        event = pyopencl.enqueue_nd_range_kernel(self.queue,kern_call, self.global_size, self.local_size,)
        event.wait()
        
        pyopencl.enqueue_copy(self.queue,  self.output, self.output_cl)
        
        data_filtered = self.output.transpose()
        
        self.output_stream().send(pos, data_filtered)
        
    def set_params(self, coefficients, nb_channel, dtype):
        self.dtype = np.dtype(dtype)
        assert self.dtype == np.dtype('float32') #TODO test if the GPU have float64 capabities and use template
        
        self.nb_channel = nb_channel
        
        #self.coefficients.shape is (nb_channel, nb_section, 6)
        #The CL kernel implement one coeficient by channel so need to to tile
        self.coefficients = coefficients.astype(self.dtype)
        if self.coefficients.ndim==2:
            self.coefficients = np.tile(self.coefficients[None,:,:], (nb_channel, 1,1))
        if not self.coefficients.flags['C_CONTIGUOUS']:
            self.coefficients = self.coefficients.copy()
        self.n_section = self.coefficients.shape[1]
        assert self.coefficients.shape[0]==self.nb_channel, 'wrong coefficients.shape'
        assert self.coefficients.shape[2]==6, 'wrong coefficients.shape'
        
        #host arrays
        self.zi = np.zeros((nb_channel, self.n_section, 2), dtype= self.dtype)
        self.output = np.zeros((self.nb_channel, self.chunksize), dtype= self.dtype)
        
        #GPU buffers
        self.coefficients_cl = pyopencl.Buffer(self.ctx, mf.READ_ONLY | mf.COPY_HOST_PTR, hostbuf=self.coefficients)
        self.zi_cl = pyopencl.Buffer(self.ctx, mf.READ_WRITE | mf.COPY_HOST_PTR, hostbuf=self.zi)
        self.input_cl = pyopencl.Buffer(self.ctx, mf.READ_WRITE, size=self.output.nbytes)
        self.output_cl = pyopencl.Buffer(self.ctx, mf.READ_WRITE, size=self.output.nbytes)
        
        #nb works
        self.global_size = (self.nb_channel, self.n_section)
        self.local_size = (1, self.n_section, )

class SosFilter(Node,  QtCore.QObject):
    """
    Node for filtering multi channel signals.
    This uses Second Order filter, it is a casde of IIR filter of order 2.
    It internally use scipy.signal.sosfilt which is available only on scipy >0.16
    
    Example:

    dev = NumpyDeviceBuffer()
    dev.configure(...)
    dev.output.configure(...)
    dev.initialize(...)
    
    f1, f2 = 40., 60.
    coefficients = scipy.signal.iirfilter(7, [f1/sample_rate*2, f2/sample_rate*2],
                btype = 'bandpass', ftype = 'butter', output = 'sos')
    filter = SosFilter()
    filter.configure(coefficients = coefficients)
    filter.input.connect(dev.output)
    filter.output.configure(...)
    filter.initialize()
    
    The coefficients.shape must be (n_section, 6).
    
    If pyopencl is avaible you can do SosFilter.configure(engine='opencl')
    In that cases the coefficients.shape can also be (n_channel, n_section, 6)
    this help for having different filter on each channels.
    
    """
    
    _input_specs = {'signals' : dict(streamtype = 'signals')}
    _output_specs = {'signals' : dict(streamtype = 'signals')}
    
    def __init__(self, parent = None, **kargs):
        QtCore.QObject.__init__(self, parent)
        Node.__init__(self, **kargs)
        assert HAVE_SCIPY, "SosFilter need scipy>0.16"
    
    def _configure(self, coefficients = None, engine='numpy', chunksize=None):
        """
        Set the coefficient of the filter.
        See http://scipy.github.io/devdocs/generated/scipy.signal.sosfilt.html for details.
        """
        self.set_coefficients(coefficients)
        self.engine = engine
        self.chunksize = chunksize

    def after_input_connect(self, inputname):
        self.nb_channel = self.input.params['nb_channel']
        for k in ['sample_rate', 'dtype', 'nb_channel', 'shape', 'timeaxis']:
            self.output.spec[k] = self.input.params[k]
    
    def _initialize(self):
        if self.engine == 'numpy':
            self.thread = SosFilterThread(self.input, self.output)
        elif  self.engine == 'opencl':
            assert HAVE_PYOPENCL, 'need pyopencl change engine to numpy'
            assert self.chunksize is not None, 'for OpenCL engine need fixed chunksize'
            self.thread = OpenCLSosFilterThread(self.input, self.output, self.chunksize)
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

register_node_type(SosFilter)



#This kernel
sos_filter_kernel = """
#define chunksize %(chunksize)d

__kernel void sos_filter(int n_section, int direction, __global  float *input,
                __global  float *output, __constant  float *coefficients, __global float *zi) {

    int chan = get_global_id(0); //channel indice
    int section = get_global_id(1); //section indice
    
    int offset_buf = chan*chunksize;
    int offset_filt = chan*n_section*6; //offset channel
    int offset_filt2;  //offset channel within section
    int offset_zi = chan*n_section*2;
    
    
    // copy channel to local group
    __local float out_channel[chunksize];
    if (section ==0) for (int s=0; s<chunksize;s++) out_channel[s] = input[offset_buf+s];
    
    float w0, w1,w2;
    float y0;
    
    w1 = zi[offset_zi+section*2+0];
    w2 = zi[offset_zi+section*2+1];
    int s2;
    for (int s=0; s<chunksize+(3*n_section);s++){
        barrier(CLK_LOCAL_MEM_FENCE);

        s2 = s-section*3;
        
        if (s2>=0 && (s2<chunksize)){
        
            if (direction==-1) s2 = chunksize - s2 - 1;  //this is for bacward
            
            offset_filt2 = offset_filt+section*6;
            w0 = out_channel[s2];
            w0 -= coefficients[offset_filt2+4] * w1;
            w0 -= coefficients[offset_filt2+5] * w2;
            out_channel[s2] = coefficients[offset_filt2+0] * w0 + coefficients[offset_filt2+1] * w1 +  coefficients[offset_filt2+2] * w2;
            w2 = w1; w1 =w0;
        }
    }
    zi[offset_zi+section*2+0] = w1;
    zi[offset_zi+section*2+1] = w2;
    
    if (section ==(n_section-1)){
        for (int s=0; s<chunksize;s++) output[offset_buf+s] = out_channel[s];
    }
    
}

"""
