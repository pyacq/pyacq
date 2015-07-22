from pyqtgraph.Qt import QtCore, QtGui

from .nodelist import register_node
from .stream import StreamDef, StreamSender, StreamReceiver
from logging import info


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
        
        self.sources = []
        self.out_streams = []
        self.in_streams = []
    
    def running(self):
        return self._running
    
    def start(self):
        raise(NotImplementedError)

    def stop(self):
        raise(NotImplementedError)
    
    def initialize(self, **kargs):
        raise(NotImplementedError)

    def configure(self, **kargs):
        raise(NotImplementedError)
    
    def create_outputs(self, streamdef_list):
        assert not self.running(), 'Cannot change source while running'
        assert len(self.out_streams)==0, 'Output Stream are already there'
        # TODO check the compatibility are of the request and the Node possiobility
        # todo check the len(self.out_streams) is the number of outputs
        for streamdef in streamdef_list:
            self.out_streams.append(StreamSender(**streamdef))
    
    def set_inputs(self, streamdef_list):
        assert not self.running(), 'Cannot change source while running'
        assert len(self.in_streams)==0, 'Input Stream are already there'
        # TODO check the compatibility are of the request and the Node possiobility
        # todo check the len(self.in_streams) is the number of outputs
        for streamdef in streamdef_list:
            self.in_streams.append(StreamReceiver(**streamdef))


class WidgetNode(Node):
    #~ need_create_widget = QtCore.Signal()
    #~ need_show_widget = QtCore.Signal()
    def __init__(self, **kargs):
        Node.__init__(self, **kargs)
        self.widget = None
        
        app = QtGui.QApplication.instance()
        #~ self.need_create_widget.connect(app.create_widget_of_node)
        #~ self.need_create_widget.emit()
        self.create_widget()
        
    def create_widget(self):
        raise(NotImplementedError)
        #self.whidget = ...
    
    def show(self):
        self.widget.show()



# For test purpos only
class _MyTest:
    def start(self):
        print(self.name, 'started')
        self._running = True
    def stop(self):
        print(self.name, 'stoped')
        self._running = False
    def initialize(self):
        pass
    def configure(self):
        pass

class _MyTestNode(_MyTest, Node):
    pass
register_node(_MyTestNode)

class _MyTestNodeQWidget(_MyTest, WidgetNode):
    def create_widget(self):
        self.widget = QtGui.QLabel('Hi!')
register_node(_MyTestNodeQWidget)