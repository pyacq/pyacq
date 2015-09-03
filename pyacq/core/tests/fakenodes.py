from pyacq import Node,WidgetNode
from pyacq.core.node import _MyTest
from pyqtgraph.Qt import QtCore, QtGui
import numpy as np

class NoneRegisteredClass(_MyTest, Node):
    pass

class FakeSender(Node):
    _output_specs = { 'signals' : {}}
    
    def _configure(self, sample_interval = 0.001):
        self.sample_interval = sample_interval
    
    def _initialize(self):
        self.n = 0
        self.timer = QtCore.QTimer(singleShot = False, interval = int(256*self.sample_interval*1000))
        self.timer.timeout.connect(self.send_data)

    def check_output_specs(self):
        spec = self.outputs['signals'].params
        assert len(spec['shape']) ==2, 'shape error'
        assert spec['shape'][1] ==16, 'shape error'
        assert spec['time_axis']==0, 'time_axis error'

    def _start(self):
        self.timer.start()

    def _stop(self):
        self.timer.stop()
    
    def _close(self):
        pass
    
    def send_data(self):
        self.n += 256
        self.outputs['signals'].send(self.n, np.random.rand(256, 16).astype('float32'))


class FakeReceiver(Node):
    _input_specs = { 'signals' : {}}

    def _configure(self, **kargs):
        print('I am node ', self.name, 'configured')

    def _initialize(self):
        self.timer = QtCore.QTimer(singleShot = False)
        self.timer.setInterval(50)
        self.timer.timeout.connect(self.poll_socket)
    
    def _start(self):
        self.timer.start()

    def _stop(self):
        self.timer.stop()

    def _close(self):
        pass
    
    def poll_socket(self):
        event = self.inputs['signals'].socket.poll(0)
        if event!=0:
            index, data = self.inputs['signals'].recv()


class ReceiverWidget(WidgetNode):
    _input_specs = { 'signals' : {}}
    
    def __init__(self, tag = 'label', **kargs):
        WidgetNode.__init__(self, **kargs)
        self.tag = tag
        self.label = QtGui.QLabel()
        self.layout = QtGui.QHBoxLayout()
        self.layout.addWidget(self.label)
        self.setLayout(self.layout)

    def _configure(self, **kargs):
        pass

    def _initialize(self):
        self.timer = QtCore.QTimer(singleShot = False)
        self.timer.setInterval(50)
        self.timer.timeout.connect(self.poll_socket)
    
    def _start(self):
        self.timer.start()

    def _stop(self):
        self.timer.stop()

    def _close(self):
        pass

    def poll_socket(self):
        event = self.inputs['signals'].socket.poll(0)
        if event!=0:
            index, data = self.inputs['signals'].recv()
            self.label.setText('{}  {}   Recv: {} {}'.format(self.name,self.tag,  index, data.shape))


