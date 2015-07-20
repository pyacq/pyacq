from pyqtgraph.Qt import QtCore

from .nodelist import register_node

class Node(QtCore.QObject):
    """
    This class:
        * is a basic element to process data stream
        * have input/output streams
        * can be a device/recorder
    """
    sources_type = [ ]
    def __init__(self, name = '', parent = None):
        QtCore.QObject.__init__(self, parent)
        self.name = name
        self._running = False
        
        self.sources = [ ]
    
    def isrunning(self):
        return self._running
    
    def start(self):
        raise(NotImplementedError)

    def stop(self):
        raise(NotImplementedError)
    
    def initialize(self, **kargs):
        raise(NotImplementedError)

    def configure(self, **kargs):
        raise(NotImplementedError)
    
    def set_sources(self, ):
        assert not self.isrunnng(), 'Cannot change source while running'
        #TODO check the source list
        #TODO create zmq.SUB socket
        pass





class _MyTestNode(Node):
    def start(self):
        print('I am node ', self.name, 'started')
        self._running = True

    def stop(self):
        print('I am node ', self.name, 'stopped')
        self._running = False
    
    def initialize(self, **kargs):
        raise(NotImplementedError)

    def configure(self, **kargs):
        raise(NotImplementedError)


register_node(_MyTestNode)
