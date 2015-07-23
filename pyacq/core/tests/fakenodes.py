from pyacq import Node,WidgetNode
from pyqtgraph.Qt import QtCore, QtGui
import numpy as np

class NoneRegisteredClass(Node):
    pass


import sys
class FakeSender(Node):
    def __init__(self, **kargs):
        Node.__init__(self, **kargs)
        #~ self.beat = QtCore.QTimer(singleShot = False, interval = 500)
        #~ self.beat.timeout.connect(self.send_data)
        #~ self.beat.timeout.connect(self.print_beat)
        #~ self.beat.start()
    
    #~ def print_beat(self):
        #~ print(self.name, 'print_beat')
        #~ sys.stdout.flush()
    
    def start(self):
        print(self.name, 'started')
        import sys
        sys.stdout.flush()
        
        self.timer.start()
        self._running = True

    def stop(self):
        self.timer.stop()
        self._running = False
    
    def close(self):
        pass
    
    def initialize(self):
        print(self.name, 'initialize')
        sys.stdout.flush()
        
        assert len(self.out_streams)!=0, 'create_outputs must be call first'
        self.stream =self.out_streams[0]
        self.n = 0
        self.timer = QtCore.QTimer(singleShot = False, interval = int(256*self.sample_interval*1000))
        #~ self.timer = QtCore.QTimer(singleShot = False, interval = 256)
        self.timer.timeout.connect(self.send_data)

    def configure(self, sample_interval = 0.001):
        self.sample_interval = sample_interval
        print(self.name, 'configure')
        import sys
        sys.stdout.flush()

    
    def send_data(self):
        print('send_data', self.n)
        import sys
        sys.stdout.flush()
        self.n += 256
        self.out_streams[0].send(self.n, np.random.rand(256, 16).astype('float32'))

class FakeReceiver(Node):
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
        #~ print(self.name, 'poll_socket')
        event = self.stream.socket.poll(0)
        if event!=0:
            index, data = self.stream.recv()
            print(self.name, 'recv', index, data.shape)


class ReceiverWidget(WidgetNode):
    def __init__(self, tag = 'label', **kargs):
        Node.__init__(self, **kargs)
        self.tag = tag
        self.label = QtGui.QLabel()
        self.widget = self.label
        
    
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
        #~ print(self.name, 'poll_socket')
        event = self.stream.socket.poll(0)
        if event!=0:
            index, data = self.stream.recv()
            #~ print(self.name, 'recv', index, data.shape)
            self.label.setText('{}  {}   Recv: {} {}'.format(self.name,self.tag, 'recv', index, data.shape))
            
            
