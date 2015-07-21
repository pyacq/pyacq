from pyqtgraph.Qt import QtCore, QtGui

from .nodelist import register_node
from .stream import StreamDef, StreamSender, StreamReceiver


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
        print('#####', self.name, len(self.out_streams))
        assert len(self.out_streams)==0, 'Output Stream are already there'
        # TODO check the compatibility are of the request and the Node possiobility
        # todo check the len(self.out_streams) is the number of outputs
        for streamdef in streamdef_list:
            self.out_streams.append(StreamReceiver(**streamdef))
    
    def set_sources(self, streamdef_list):
        assert not self.running(), 'Cannot change source while running'
        assert len(self.in_streams)==0, 'Input Stream are already there'
        # TODO check the compatibility are of the request and the Node possiobility
        # todo check the len(self.in_streams) is the number of outputs
        for streamdef in streamdef_list:
            self.in_streams.append(StreamReceiver(**streamdef))


class WidgetNode(Node):
    need_create_widget = QtCore.Signal()
    need_show_widget = QtCore.Signal()
    def __init__(self, **kargs):
        Node.__init__(self, **kargs)
        self.widget = None
        
        app = QtGui.QApplication.instance()
        self.need_create_widget.connect(app.create_widget_of_node)
        self.need_show_widget.connect(app.show_widget_of_node)        
        self.need_create_widget.emit()
        
    def create_widget(self):
        raise(NotImplementedError)
    
    def show(self):
        self.need_show_widget.emit()






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



class _MyTestNodeQWidget(WidgetNode):
    def create_widget(self):
        self.widget = QtGui.QLabel('Hi!')
register_node(_MyTestNodeQWidget)


