from pyqtgraph.Qt import QtCore


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
        self.running = False
        
        self.sources = [ ]
    
    def isrunning(self):
        return self.running
    
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


