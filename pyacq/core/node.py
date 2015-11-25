from pyqtgraph.Qt import QtCore, QtGui
from pyqtgraph.util.mutex import Mutex

from .nodelist import register_node_type
from .stream import OutputStream, InputStream
from logging import info


class Node(object):
    """
    A Node is the basic element for generating and processing data streams
    in pyacq. 
    
    Nodes may be used to interact with devices, generate data, store data, 
    perform computations, or display user interfaces. Each node may have multiple
    input and output streams that connect to other nodes. For example::
    
       [ data acquisition node ] -> [ processing node ] -> [ display node ]
                                                        -> [ recording node ]
    
    An application may directly create and connect the Nodes it needs, or it
    may use a Manager to create a network of nodes distributed across multiple
    processes or machines.
    
    The order of operations when creating and operating a node is very important:
    
    1. Instantiate the node directly or remotely using `NodeGroup.create_node`.
    2. Call `Node.configure(...)` to set global parameters such as sample rate,
       channel selections, etc.
    3. Connect inputs to their sources (if applicable):
       `Node.inputs['input_name'].connect(other_node.outpouts['output_name'])`
    4. Configure outputs: `Node.outputs['output_name'].configure(...)`
    5. Call `Node.initialize()`, which will verify input/output settings, 
       allocate memory, prepare devices, etc.
    6. Call `Node.start()` and `Node.stop()` to begin/end reading from input 
       streams and writing to output streams. These may be called multiple times.
    7. Close the node with `Node.close()`. If the node was created remotely, 
       this is handled by the NodeGroup to which it belongs.
    
    Notes
    -----
    
    For convenience, if a Node has only 1 input or 1 output:
    
    * `Node.inputs['input_name']` can be written `Node.input`
    * `Node.outputs['output_name']` can be written `Node.output`
    
    When there are several outputs or inputs, this shorthand is not permitted.
    
    The state of a Node can be requested using thread-safe methods:
    
    * `Node.running()`
    * `Node.configured()`
    * `Node.initialized()`
    """
    _input_specs = {}
    _output_specs = {}
    
    def __init__(self, name='', parent=None):
        self.name = name
        
        self.lock = Mutex()  # on lock for all state
        self._running = False
        self._configured = False
        self._initialized = False
        self._closed = False
        
        self.inputs = {name:InputStream(spec=spec, node=self, name=name) for name, spec in self._input_specs.items()}
        self.outputs = {name:OutputStream(spec=spec, node=self, name=name) for name, spec in self._output_specs.items()}
    
    @property
    def input(self):
        """Return the single input for this Node.
        
        If the node does not have exactly one input, then raise AssertionError.
        """
        assert len(self.inputs)==1, 'Node.input is a shortcut when Node have only 1 input ({} here)'.format(len(self.inputs))
        return list(self.inputs.values())[0]
    
    @property
    def output(self):
        """Return the single output for this Node.
        
        If the node does not have exactly one put, then raise AssertionError.
        """
        assert len(self.outputs)==1, 'Node.output is a shortcut when Node have only 1 output ({} here)'.format(len(self.outputs))
        return list(self.outputs.values())[0]
    
    def running(self):
        """Return True if the Node is running.
        
        This method is thread-safe.
        """
        with self.lock:
            return self._running
    
    def configured(self):
        """Return True if the Node has already been configured.
        
        This method is thread-safe.
        """
        with self.lock:
            return self._configured

    def initialized(self):
        """Return True if the Node has already been initialized.
        
        This method is thread-safe.
        """
        with self.lock:
            return self._initialized
    
    def closed(self):
        """Return True if the Node has already been closed.
        
        This method is thread-safe.
        """
        with self.lock:
            return self._closed
    
    def configure(self, **kargs):
        """Configure the Node.
        
        This method is used to set global parameters such as sample rate,
        channel selections, etc. Each Node subclass determines the allowed
        arguments to this method by reimplementing `Node._configure()`.
        """
        assert not self.running(),\
                'Cannot configure Node {} : the Node is running'.format(self.name)
        self._configure(**kargs)
        with self.lock:
            self._configured = True
    
    def initialize(self):
        """Initialize the Node.
        
        This method prepares the node for operation by allocating memory, 
        preparing devices, checking input and output specifications, etc.
        Node subclasses determine the behavior of this method by reimplementing
        `Node._initialize()`.
        """
        self.check_input_specs()
        self.check_output_specs()
        self._initialize()
        with self.lock:
            self._initialized = True

    def start(self):
        """Start the Node.
        
        When the node is running it will read from its input streams and write
        to its output streams (if any). Nodes must be configured and initialized
        before they are started, and can be stopped and restarted any number of
        times.
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
        """Stop the Node (see `start()`).
        """
        assert self.running(),\
            'Cannot stop Node {} : the Node is not running'.format(self.name)

        self._stop()
        with self.lock:
            self._running = False
    
    def close(self):
        """Close the Node.
        
        This causes all input/output connections to be closed. Nodes must
        be stopped before they can be closed.
        """
        assert not self.running(),\
                'Cannot close Node {} : the Node is running'.format(self.name)
        with self.lock:
            if self._closed:
                return
        self._close()
        for input in self.inputs.values():
            input.close()
        for output in self.outputs.values():
            output.close()
        with self.lock:
            self._configured = False
            self._initialized = False
            self._closed = True
    
    def _configure(self, **kargs):
        """This method is called during `Node.configure()` and must be
        reimplemented by subclasses.
        """
        raise(NotImplementedError)

    def _initialize(self, **kargs):
        """This method is called during `Node.initialize()` and must be
        reimplemented by subclasses.
        """
        raise(NotImplementedError)
    
    def _start(self):
        """This method is called during `Node.start()` and must be
        reimplemented by subclasses.
        """
        raise(NotImplementedError)
    
    def _stop(self):
        """This method is called during `Node.stop()` and must be
        reimplemented by subclasses.
        """
        raise(NotImplementedError)

    def _close(self, **kargs):
        """This method is called during `Node.close()` and must be
        reimplemented by subclasses.
        """
        raise(NotImplementedError)
    
    def check_input_specs(self):
        """This method is called during `Node.initialize()` and may be
        reimplemented by subclasses to ensure that inputs are correctly
        configured before the node is started.
        
        In case of misconfiguration, this method must raise an exception.
        """
        pass
    
    def check_output_specs(self):
        """This method is called during `Node.initialize()` and may be
        reimplemented by subclasses to ensure that outputs are correctly
        configured before the node is started.
        
        In case of misconfiguration, this method must raise an exception.
        """
        pass
    
    def after_input_connect(self, inputname):
        """This method is called when one of the Node's inputs has been
        connected.
        
        It may be reimplemented by subclasses.
        """
        pass
    
    def after_output_configure(self, outputname):
        """This method is called when one of the Node's outputs has been
        configured.
        
        It may be reimplemented by subclasses.
        """
        pass
    


class WidgetNode(QtGui.QWidget, Node):
    """Base class for Nodes that implement a QWidget user interface.
    """
    def __init__(self, parent=None, **kargs):
        QtGui.QWidget.__init__(self, parent=parent)
        Node.__init__(self, **kargs)
    
    def close(self):
        Node.close(self)
        QtGui.QWidget.close(self)

    def closeEvent(self,event):
        if self.running():
            self.stop()
        if not self.closed():
            Node.close(self)
        event.accept()

        


# For test purposes only
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
