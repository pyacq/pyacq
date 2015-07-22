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
    need_create_widget = QtCore.Signal()
    need_show_widget = QtCore.Signal()
    def __init__(self, **kargs):
        Node.__init__(self, **kargs)
        self.widget = None
        
        app = QtGui.QApplication.instance()
        self.need_create_widget.connect(app.create_widget_of_node)
        self.need_create_widget.emit()
        self.create_widget()
        
    def create_widget(self):
        raise(NotImplementedError)
        #self.whidget = ...
    
    def show(self):
        self.widget.show()






class _MyTestNode(Node):
    def start(self):
        print('I am node ', self.name, 'started')
        self._running = True

    def stop(self):
        print('I am node ', self.name, 'stopped')
        self._running = False

    def configure(self, **kargs):
        print('I am node ', self.name, 'configured')
    
    def initialize(self, **kargs):
        print('I am node ', self.name, 'initialized')
register_node(_MyTestNode)



class _MyTestNodeQWidget(WidgetNode):
    def create_widget(self):
        self.widget = QtGui.QLabel('Hi!')
register_node(_MyTestNodeQWidget)


class _MyReceiverNode(Node):
    def __init__(self, **kargs):
        Node.__init__(self, **kargs)
    
    def start(self):
        self.timer.start()
        self._running = True

    def stop(self):
        self.timer.stop()
        self._running = False
    
    def close(self):
        pass
    
    def initialize(self):
        assert len(self.in_streams)!=0, 'create_outputs must be call first'
        self.stream =self.in_streams[0]
        
        self.timer = QtCore.QTimer(singleShot = False)
        self.timer.setInterval(50)
        self.timer.timeout.connect(self.poll_socket)

    def configure(self, **kargs):
        print('I am node ', self.name, 'configured')
    
    def poll_socket(self):
        print(self._name, 'poll_socket')
        event = self.stream.socket.poll(0)
        if event!=0:
            index, data = self.stream.recv()
            print(self.name, 'recv', index)
        
register_node(_MyReceiverNode)
