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
        self.n_sections = coefficients.shape[0]
        self.zi = np.zeros((self.n_sections, 2, nb_channel), dtype= dtype)



class SosFilter(Node,  QtCore.QObject):
    _input_specs = {'signals' : dict(streamtype = 'signals')}
    _output_specs = {'signals' : dict(streamtype = 'signals')}
    
    def __init__(self, parent = None, **kargs):
        QtCore.QObject.__init__(self, parent)
        Node.__init__(self, **kargs)
        assert HAVE_SCIPY, "SosFilter need scipy>0.16"
    
    def _configure(self, coefficients = None):
        self.set_coefficients(coefficients)

    def after_input_connect(self, inputname):
        self.nb_channel = self.input.params['nb_channel']
        for k in ['sample_rate', 'dtype', 'nb_channel', 'shape', 'timeaxis']:
            self.output.spec[k] = self.input.params[k]
    
    def after_output_configure(self, outputname):
        print(self.output.params)

    def _initialize(self):
        self.thread = SosFilterThread(self.input, self.output)
        self.thread.set_params(self.coefficients, self.nb_channel, self.output.params['dtype'])
    
    def _start(self):
        self.thread.last_pos = None
        self.thread.start()
    
    def _stop(self):
        self.thread.stop()
        self.thread.wait()
    
    def on_params_change(self):
        self.new_params.emit(self.params)
    
    def set_coefficients(self, coefficients):
        self.coefficients = coefficients
        if self.initialized():
            self.thread.set_params(self.coefficients, self.nb_channel, self.output.params['dtype'])

register_node_type(SosFilter)