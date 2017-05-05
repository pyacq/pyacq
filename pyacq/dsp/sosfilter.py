# -*- coding: utf-8 -*-
# Copyright (c) 2016, French National Center for Scientific Research (CNRS)
# Distributed under the (new) BSD License. See LICENSE for more info.

from pyqtgraph.Qt import QtCore
import pyqtgraph as pg
from pyqtgraph.util.mutex import Mutex
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

#TODO: make a kernel that mix SosFilter_OpenCL_V1 and SosFilter_OpenCL_V2 approach


class SosFilter_Scipy:
    """
    Implementation with scipy.
    """
    def __init__(self, coefficients, nb_channel, dtype, chunksize):
        self.coefficients = coefficients
        self.nb_section = coefficients.shape[0]
        self.nb_channel = nb_channel
        self.zi = np.zeros((self.nb_section, 2, self.nb_channel), dtype= dtype)
        self.dtype=dtype
        self.chunksize = chunksize
    
    def compute_one_chunk(self, pos, chunk):
        chunk_filtered, self.zi = scipy.signal.sosfilt(self.coefficients, chunk, zi = self.zi, axis = 0)
        chunk_filtered = chunk_filtered.astype(self.dtype)
        return chunk_filtered


class SosFilter_OpenCl_Base:
    def __init__(self, coefficients, nb_channel, dtype, chunksize):
        self.dtype = np.dtype(dtype)
        assert self.dtype == np.dtype('float32')
        self.nb_channel = nb_channel
        self.chunksize = chunksize
        assert self.chunksize is not None, 'chunksize for opencl must be fixed'
        
        self.coefficients = coefficients.astype(self.dtype)
        if self.coefficients.ndim==2: #(nb_section, 6) to (nb_channel, nb_section, 6)
            self.coefficients = np.tile(self.coefficients[None,:,:], (nb_channel, 1,1))
        if not self.coefficients.flags['C_CONTIGUOUS']:
            self.coefficients = self.coefficients.copy()
        self.nb_section = self.coefficients.shape[1]
        
        assert self.coefficients.shape[0]==self.nb_channel, 'wrong coefficients.shape'
        assert self.coefficients.shape[2]==6, 'wrong coefficients.shape'

        self.ctx = pyopencl.create_some_context()
        #TODO : add arguments gpu_platform_index/gpu_device_index
        #self.devices =  [pyopencl.get_platforms()[self.gpu_platform_index].get_devices()[self.gpu_device_index] ]
        #self.ctx = pyopencl.Context(self.devices)        
        self.queue = pyopencl.CommandQueue(self.ctx)
        
        #host arrays
        self.zi = np.zeros((nb_channel, self.nb_section, 2), dtype= self.dtype)
        
        #GPU buffers
        nbytes = self.chunksize * self.nb_channel * self.dtype.itemsize
        self.coefficients_cl = pyopencl.Buffer(self.ctx, mf.READ_ONLY | mf.COPY_HOST_PTR, hostbuf=self.coefficients)
        self.zi_cl = pyopencl.Buffer(self.ctx, mf.READ_WRITE | mf.COPY_HOST_PTR, hostbuf=self.zi)
        self.input_cl = pyopencl.Buffer(self.ctx, mf.READ_WRITE, size=nbytes)
        self.output_cl = pyopencl.Buffer(self.ctx, mf.READ_WRITE, size=nbytes)
        
        #nb works
        kernel = self.kernel%dict(chunksize = self.chunksize, nb_section=self.nb_section, nb_channel=self.nb_channel)
        prg = pyopencl.Program(self.ctx, kernel)
        self.opencl_prg = prg.build(options='-cl-mad-enable')


class SosFilter_OpenCL_V1(SosFilter_OpenCl_Base):
    """
    Implementation with OpenCL : this version scale nb_channel.
    """
    def __init__(self, coefficients, nb_channel, dtype, chunksize):
        SosFilter_OpenCl_Base.__init__(self, coefficients, nb_channel, dtype, chunksize)
        self.global_size = (self.nb_channel, )
        self.local_size = (self.nb_channel, )
        self.output = np.zeros((self.chunksize, self.nb_channel), dtype= self.dtype)
        self.kernel_func_name = 'sos_filter'
    
    def compute_one_chunk(self, pos, chunk):
        assert chunk.dtype==self.dtype
        assert chunk.shape==(self.chunksize, self.nb_channel), 'wrong shape'
        
        if not chunk.flags['C_CONTIGUOUS']:
            chunk = chunk.copy()
        pyopencl.enqueue_copy(self.queue,  self.input_cl, chunk)

        kern_call = getattr(self.opencl_prg, self.kernel_func_name)
        event = kern_call(self.queue, self.global_size, self.local_size,
                                self.input_cl, self.output_cl, self.coefficients_cl, self.zi_cl)
        event.wait()
        
        pyopencl.enqueue_copy(self.queue,  self.output, self.output_cl)
        chunk_filtered = self.output
        return chunk_filtered
    
    kernel = """
    #define chunksize %(chunksize)d
    #define nb_section %(nb_section)d
    #define nb_channel %(nb_channel)d

    __kernel void sos_filter(__global  float *input, __global  float *output, __constant  float *coefficients, 
                                                                            __global float *zi) {

        int chan = get_global_id(0); //channel indice
        
        int offset_filt2;  //offset channel within section
        int offset_zi = chan*nb_section*2;
        
        int idx;

        float w0, w1,w2;
        float res;
        
        for (int section=0; section<nb_section; section++){
        
            offset_filt2 = chan*nb_section*6+section*6;
            
            w1 = zi[offset_zi+section*2+0];
            w2 = zi[offset_zi+section*2+1];
            
            for (int s=0; s<chunksize;s++){
                
                idx = s*nb_channel+chan;
                if (section==0)  {w0 = input[idx];}
                else {w0 = output[idx];}
                
                w0 -= coefficients[offset_filt2+4] * w1;
                w0 -= coefficients[offset_filt2+5] * w2;
                res = coefficients[offset_filt2+0] * w0 + coefficients[offset_filt2+1] * w1 +  coefficients[offset_filt2+2] * w2;
                w2 = w1; w1 =w0;
                
                output[idx] = res;
            }
            
            zi[offset_zi+section*2+0] = w1;
            zi[offset_zi+section*2+1] = w2;

        }
       
    }
    
    
    """


class SosFilter_OpenCL_V2:
    """
    Implementation with OpenCL : this version scale nb_section.
    """
    def __init__(self, coefficients, nb_channel, dtype, chunksize):
        SosFilter_OpenCl_Base.__init__(self, coefficients, nb_channel, dtype, chunksize)
        self.global_size = (self.nb_channel, self.nb_section)
        self.local_size = (1, self.nb_section, )
        self.output = np.zeros((self.nb_channel,self.chunksize), dtype= self.dtype)
        self.kernel_func_name = 'sos_filter'
        
    def compute_one_chunk(self, pos, chunk):
        assert chunk.dtype==self.dtype
        assert chunk.shape==(self.chunksize, self.nb_channel), 'wrong shape'
        
        chunk = chunk.transpose()
        if not chunk.flags['C_CONTIGUOUS']:
            chunk = chunk.copy()
        pyopencl.enqueue_copy(self.queue,  self.input_cl, chunk)

        kern_call = getattr(self.opencl_prg, self.kernel_func_name)
        event = kern_call(self.queue, self.global_size, self.local_size,
                                self.input_cl, self.output_cl, self.coefficients_cl, self.zi_cl)
        event.wait()
        
        pyopencl.enqueue_copy(self.queue,  self.output, self.output_cl)
        chunk_filtered = self.output.transpose()
        return chunk_filtered
    
    kernel = """
    #define chunksize %(chunksize)d
    #define nb_section %(nb_section)d
    #define nb_channel %(nb_channel)d

    __kernel void sos_filter(__global  float *input, __global  float *output, 
                                                __constant  float *coefficients, __global float *zi) {

        int chan = get_global_id(0); //channel indice
        int section = get_global_id(1); //section indice

        int offset_buf = chan*chunksize;
        int offset_filt = chan*nb_section*6; //offset channel
        int offset_filt2;  //offset channel within section
        int offset_zi = chan*nb_section*2;


        // copy channel to local group
        __local float out_channel[chunksize];
        if (section ==0) for (int s=0; s<chunksize;s++) out_channel[s] = input[offset_buf+s];
        
        float w0, w1,w2;
        float y0;
        
        w1 = zi[offset_zi+section*2+0];
        w2 = zi[offset_zi+section*2+1];
        int s2;
        for (int s=0; s<chunksize+(3*nb_section);s++){
            barrier(CLK_LOCAL_MEM_FENCE);

            s2 = s-section*3;
            
            if (s2>=0 && (s2<chunksize)){
            
//                if (direction==-1) s2 = chunksize - s2 - 1;  //this is for bacward
                
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
        
        if (section ==(nb_section-1)){
            for (int s=0; s<chunksize;s++) output[offset_buf+s] = out_channel[s];
        }
       
    }
    
    """


class SosFilter_OpenCL_V3(SosFilter_OpenCl_Base):
    """
    Implementation with OpenCL : similar to SosFilter_OpenCL_V2 but with global
    memory and no transpose on host.
    """
    def __init__(self, coefficients, nb_channel, dtype, chunksize):
        SosFilter_OpenCl_Base.__init__(self, coefficients, nb_channel, dtype, chunksize)
        self.global_size = (self.nb_channel, self.nb_section)
        self.local_size = (1, self.nb_section)
        self.output = np.zeros((self.chunksize, self.nb_channel), dtype= self.dtype)
        self.kernel_func_name = 'sos_filter'
    
    def compute_one_chunk(self, pos, chunk):
        assert chunk.dtype==self.dtype
        assert chunk.shape==(self.chunksize, self.nb_channel), 'wrong shape'
        
        if not chunk.flags['C_CONTIGUOUS']:
            chunk = chunk.copy()
        pyopencl.enqueue_copy(self.queue,  self.input_cl, chunk)

        kern_call = getattr(self.opencl_prg, self.kernel_func_name)
        event = kern_call(self.queue, self.global_size, self.local_size,
                                self.input_cl, self.output_cl, self.coefficients_cl, self.zi_cl)
        event.wait()
        
        pyopencl.enqueue_copy(self.queue,  self.output, self.output_cl)
        chunk_filtered = self.output
        return chunk_filtered
    
    kernel = """
    #define chunksize %(chunksize)d
    #define nb_section %(nb_section)d
    #define nb_channel %(nb_channel)d

    __kernel void sos_filter(__global  float *input, __global  float *output, __constant  float *coefficients, 
                                                                            __global float *zi) {

        int chan = get_global_id(0); //channel indice
        int section = get_global_id(1); //section indice
        
        int offset_filt2;  //offset channel within section
        int offset_zi = chan*nb_section*2;
        
        int idx;

        float w0, w1,w2;
        float res;
        int s2;

        w1 = zi[offset_zi+section*2+0];
        w2 = zi[offset_zi+section*2+1];
        
        for (int s=0; s<chunksize+(3*nb_section);s++){
            barrier(CLK_GLOBAL_MEM_FENCE);

            s2 = s-section*3;
            
            if (s2>=0 && (s2<chunksize)){
                
                offset_filt2 = chan*nb_section*6+section*6;
                
                idx = s2*nb_channel+chan;
                if (section==0)  {w0 = input[idx];}
                else {w0 = output[idx];}
                
                w0 -= coefficients[offset_filt2+4] * w1;
                w0 -= coefficients[offset_filt2+5] * w2;
                res = coefficients[offset_filt2+0] * w0 + coefficients[offset_filt2+1] * w1 +  coefficients[offset_filt2+2] * w2;
                w2 = w1; w1 =w0;
                
                output[idx] = res;
            }
        }

        zi[offset_zi+section*2+0] = w1;
        zi[offset_zi+section*2+1] = w2;        
       
    }
    
    
    """



sosfilter_engines = { 'scipy' : SosFilter_Scipy, 'opencl' : SosFilter_OpenCL_V1,
                'opencl2' : SosFilter_OpenCL_V2, 'opencl3' : SosFilter_OpenCL_V3, }
    


class SosFilterThread(ThreadPollInput):
    def __init__(self, input_stream, output_stream, timeout = 200, parent = None):
        ThreadPollInput.__init__(self, input_stream, timeout = timeout, return_data=True, parent = parent)
        self.output_stream = output_stream
        self.mutex = Mutex()

    def process_data(self, pos, data):
        with self.mutex:
            chunk_filtered = self.filter_engine.compute_one_chunk(pos, data)
        self.output_stream.send(chunk_filtered, index=pos)
        
    def set_params(self, engine, coefficients, nb_channel, dtype, chunksize):
        assert engine in sosfilter_engines
        EngineClass = sosfilter_engines[engine]
        with self.mutex:
            self.filter_engine = EngineClass(coefficients, nb_channel, dtype, chunksize)


class SosFilter(Node,  QtCore.QObject):
    """
    Node for filtering multi channel signals.
    This uses a second order filter, it is a casde of IIR filter of order 2.
    It internally uses scipy.signal.sosfilt which is available only on scipy >0.16
    
    Example::

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
    
    The ``coefficients.shape`` must be (nb_section, 6).
    
    If pyopencl is avaible you can use ``SosFilter.configure(engine='opencl')``.
    In that case the coefficients.shape can also be (nb_channel, nb_section, 6)
    this helps for having different filters on each channel.
    
    The opencl engine inernally requires data to be in (channel, sample) order.
    If the input data does not have this order, then it must be copied and
    performance will be affected.
    """
    
    _input_specs = {'signals' : dict(streamtype = 'signals')}
    _output_specs = {'signals' : dict(streamtype = 'signals')}
    
    def __init__(self, parent = None, **kargs):
        QtCore.QObject.__init__(self, parent)
        Node.__init__(self, **kargs)
        assert HAVE_SCIPY, "SosFilter need scipy>0.16"
    
    def _configure(self, coefficients = None, engine='scipy', chunksize=None):
        """
        Set the coefficient of the filter.
        See http://scipy.github.io/devdocs/generated/scipy.signal.sosfilt.html for details.
        """
        self.set_coefficients(coefficients)
        self.engine = engine
        self.chunksize = chunksize

    def after_input_connect(self, inputname):
        self.nb_channel = self.input.params['shape'][1]
        for k in ['sample_rate', 'dtype', 'shape']:
            self.output.spec[k] = self.input.params[k]
    
    def _initialize(self):
        self.thread = SosFilterThread(self.input, self.output)
        self.thread.set_params(self.engine, self.coefficients, self.nb_channel,
                            self.output.params['dtype'], self.chunksize)
    
    def _start(self):
        self.thread.last_pos = None
        self.thread.start()
    
    def _stop(self):
        self.thread.stop()
        self.thread.wait()
    
    def set_coefficients(self, coefficients):
        self.coefficients = coefficients
        if self.initialized():
            self.thread.set_params(self.engine, self.coefficients, self.nb_channel,
                                self.output.params['dtype'], self.chunksize)


register_node_type(SosFilter)
