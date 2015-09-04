from pyqtgraph.Qt import QtCore, QtGui
from pyqtgraph.util.mutex import Mutex

from .nodelist import register_node_type
from .stream import OutputStream, InputStream
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
        * initialize() : open the device or setup memory and checkup output outputs specifications.
          Must be done before Node.start()
    
    Usage of a Node, the **order** is important:
        1 - Instanciate : directly or remotly Node with NodeGroup.creat_node
        2 - Node.configure(...)
        3 - Connect Input (if have input) : Node.inputs['input_name'].connect(other_node.outpouts['output_name'])
        4 - Configure outputs : Node.outputs['output_name'].configure(...)
        5 - initialize : Node.initialize(), this also check inputs and outputs specifications.
        6 - Start/Stop many time : Node.start()/Node.stop()
        7 - Node.close() : done by NodeGroup if the Node is remoted
    
    Note :
    For convenience, if a Node have only 1 Input or 1 output:
       * `Node.inputs['input_name']` can be written `Node.input`
       * `Node.outputs['output_name']` can be written `Node.output`
    When there is several outputs or inputs it is not possible.
    
    States of Node are accessible with method and it is thread safe:
        * Node.running()
        * Node.configured()
        * Node.initialize()
        
    
        
    """
    _input_specs = { }
    _output_specs = { }
    
    def __init__(self, name = '', parent = None):
        QtCore.QObject.__init__(self, parent)
        self.name = name
        
        self.lock = Mutex() # on lock for all state
        self._running = False
        self._configured = False
        self._initialized = False
        
        
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
        """get the running state of the Node (thread safe)
        """
        with self.lock:
            return self._running
    
    def configured(self):
        """get the configured state of the Node (thread safe)
        """
        with self.lock:
            return self._configured

    def initialized(self):
        """get the initialized state of the Node (thread safe)
        """
        with self.lock:
            return self._initialized
    
    def configure(self, **kargs):
        """Configure the Node
        """
        assert not self.running(),\
                'Cannot configure Node {} : the Node is running'.format(self.name)
        self._configure(**kargs)
        with self.lock:
            self._configured = True
    
    def initialize(self):
        """Initialize the Node.
        This also check inputs and outputs specifications.
        """
        self.check_input_specs()
        self.check_output_specs()
        self._initialize()
        with self.lock:
            self._initialized = True


    def start(self):
        """This start the Node.
        """
        assert self.configured(),\
            'Cannot start Node {} : the Node is not configured'.format(self.name)
        assert self.initialized(),\
            'Cannot start Node {} : the Node is not initialized'.format(self.name)
        assert not self.running(),\
            'Cannot start Node {} : the Node is already running'.format(self.name)
        
        self._start()
        with self.lock:
            self._running = True

    def stop(self):
        """This stop the Node
        """
        assert self.running(),\
            'Cannot stop Node {} : the Node is not running'.format(self.name)

        self._stop()
        with self.lock:
            self._running = False
    
    def close(self):
        """Close the Node
        """
        assert not self.running(),\
                'Cannot close Node {} : the Node is running'.format(self.name)
        self._close()
        with self.lock:
            self._configured = False
            self._initialized = False
    
    #That method MUST be overwritten
    def _configure(self, **kargs):
        raise(NotImplementedError)

    #That method MUST be overwritten
    def _initialize(self, **kargs):
        raise(NotImplementedError)
    
    #That method MUST be overwritten
    def _start(self):
        raise(NotImplementedError)
    
    #That method MUST be overwritten
    def _stop(self):
        raise(NotImplementedError)

    #That method MUST be overwritten
    def _close(self, **kargs):
        raise(NotImplementedError)
    
    #That method SHOULD be overwritten
    def check_input_specs(self):
        pass
    
    #That method SHOULD be overwritten
    def check_output_specs(self):
        pass
    


class WidgetNode(QtGui.QWidget, Node, ):
    def __init__(self, parent = None, **kargs):
        QtGui.QWidget.__init__(self, parent = parent)
        Node.__init__(self, **kargs)
    
    def close(self):
        QtGui.QWidget.close(self)
        Node.close(self)


# For test purpos only
class _MyTest:
    def _initialize(self): pass
        
    def _configure(self): pass
    
    def _start(self): pass
        
    def _stop(self): pass
    
    def _close(self): pass


class _MyTestNode(_MyTest, Node):
    pass
register_node_type(_MyTestNode)

class _MyTestNodeQWidget(_MyTest, WidgetNode):
    pass
register_node_type(_MyTestNodeQWidget)
