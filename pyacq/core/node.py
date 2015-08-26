from pyqtgraph.Qt import QtCore, QtGui

from .nodelist import register_node_type
from .stream import StreamDef, OutputStream, InputStream
from logging import info


class Node(QtCore.QObject):
    """
    This class:
        * is a basic element to process data stream
        * have several input/output streams
        * can be a device/recorder/processor
        * instanciated by NodeGroup or in local QApp
        * remote by NodeGroup (RPC) or in the main QApplication directly (usefull for WidgetNode).
        * start()/stop() : mean listen on input sockets and write to output sockets
        * configuration() : done when not running. Set global params, ex: sampling_rate, selected channel, ...
        * initialize() : open the device or setup memory
        
        
    """
    _input_specs = { }
    _output_specs = { }
    
    def __init__(self, name = '', parent = None):
        QtCore.QObject.__init__(self, parent)
        self.name = name
        self._running = False
        
        self.inputs = { name:InputStream(spec = spec) for name, spec in self._input_specs.items() }
        self.outputs = { name:OutputStream(spec = spec) for name, spec in self._output_specs.items() }
    
    @property
    def input(self):
        """Shortcut when only 1 inputs"""
        assert len(self.inputs)==1, 'Node.input is a shortcut when Node have only 1 input ({} here)'.format(len(self.inputs))
        return list(self.inputs.values())[0]
    
    @property
    def output(self):
        """Shortcut when only 1 output"""
        assert len(self.outputs)==1, 'Node.output is a shortcut when Node have only 1 output ({} here)'.format(len(self.outputs))
        return list(self.outputs.values())[0]
    
    def connect_input(self, name, stream_spec):
        """This is usefull for the InputStreamProxy
        """
        self.inputs[name].connect(stream_spec)
    
    def configure_output(self, name, **stream_spec):
        """This is usefull for the OutputStreamProxy
        """
        self.outputs[name].configure(**stream_spec)
    
    def  get_output(self, name):
        """This is usefull for the OutputStreamProxy
        """
        return self.outputs[name].params

    
    def running(self):
        return self._running
    
    def start(self):
        raise(NotImplementedError)

    def stop(self):
        raise(NotImplementedError)

    def configure(self, **kargs):
        raise(NotImplementedError)
    
    def check_input_specs(self):
        pass

    def check_output_specs(self):
        pass

    def _initialize(self, **kargs):
        """
        Need to be implemented for a devcie.
        """
        raise(NotImplementedError)
    
    def initialize(self):
        # inputs
        self.check_input_specs()
        self.check_output_specs()
        self._initialize()


class WidgetNode(QtGui.QWidget, Node, ):
    def __init__(self, parent = None, **kargs):
        QtGui.QWidget.__init__(self, parent = parent)
        Node.__init__(self, **kargs)



# For test purpos only
class _MyTest:
    def start(self):
        self._running = True
    def stop(self):
        self._running = False
    def _initialize(self):
        pass
    def configure(self):
        pass

class _MyTestNode(_MyTest, Node):
    pass
register_node_type(_MyTestNode)

class _MyTestNodeQWidget(_MyTest, WidgetNode):
    pass
register_node_type(_MyTestNodeQWidget)
