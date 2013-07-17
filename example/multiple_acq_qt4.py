# -*- coding: utf-8 -*-
"""
Multiple acquisition with several device at different sampling_rate.
Use a mixt of gevent and Qt4.


"""

from pyacq import StreamHandler, FakeMultiSignals, TimestampServer
import msgpack
import gevent
import zmq

import os,sys
from PyQt4 import QtCore,QtGui

from pyacq import StreamHandler, FakeMultiSignals, TimestampServer
from collections import OrderedDict



sampling_rates = [10., 100., 1000., 50000.]
packet_sizes =  [4, 32, 64, 128*4]
nb_devices = 4

class ControlStartSop(QtGui.QWidget):
    def __init__(self,  devices = None, streamhandler = None, timestampserver = None, 
                                            parent = None,):
        QtGui.QWidget.__init__(self, parent)
        
        self.streamhandler = streamhandler
        self.timestampserver = timestampserver
        self.devices = devices
        
        self.context = zmq.Context()
        
        mainlayout = QtGui.QVBoxLayout()
        self.setLayout(mainlayout)
        
        grid = QtGui.QGridLayout()
        mainlayout.addLayout(grid)
        
        self.start_buttons = [ ]
        self.stop_buttons = [ ]
        for i, dev in enumerate(self.devices):
            grid.addWidget(QtGui.QLabel('Dev.anme {} rate {}hz Port {}'.format(dev.name, dev.sampling_rate, dev.stream['port'])),i, 0)
            
            but = QtGui.QPushButton('start #{}'.format(i))
            but.clicked.connect(self.start_device)
            grid.addWidget(but,i, 1)
            self.start_buttons.append(but)
            
            but = QtGui.QPushButton('strop #{}'.format( i))
            but.clicked.connect(self.stop_device)
            grid.addWidget(but,i, 2)
            self.stop_buttons.append(but)
    
    def start_device(self):
        i = self.start_buttons.index(self.sender())
        if not self.devices[i].running:
            self.devices[i].start()
            self.timestampserver.follow_stream(self.devices[i].stream)

    def stop_device(self):
        i = self.stop_buttons.index(self.sender())
        if  self.devices[i].running:
            self.devices[i].stop()
            self.timestampserver.leave_stream(self.devices[i].stream)
    

class RecvThread(QtCore.QThread):
    newpacket = QtCore.pyqtSignal(int, int)
    
    def __init__(self, parent=None, socket = None, port=None):
        QtCore.QThread.__init__(self, parent)
        self.running = False
        self.socket = socket
        self.port = port
    
    def run(self):
        self.running = True
        while self.running:
            message = self.socket.recv()
            pos = msgpack.loads(message)
            self.newpacket.emit(self.port, pos)


class PlotRecvPacket(QtGui.QWidget):
    
    newpacket = QtCore.pyqtSignal(int, int)
    
    def __init__(self, parent = None, streamhandler = None, 
                                timestampserver =None):
        QtGui.QWidget.__init__(self, parent)

        self.streamhandler = streamhandler
        self.timestampserver = timestampserver
        
        self.context = zmq.Context()
        
        mainlayout = QtGui.QVBoxLayout()
        self.setLayout(mainlayout)
        grid = QtGui.QGridLayout()
        mainlayout.addLayout(grid)
        
        self.labels = OrderedDict()
        self.labels2 = OrderedDict()
        self.sockets = OrderedDict()
        self.threads = OrderedDict()
        
        for port, stream in self.streamhandler.streams.items():
            i = self.streamhandler.streams.keys().index(port)
            l = QtGui.QLabel('nothing')
            grid.addWidget(l,i, 0)
            self.labels[port] = l
            l = QtGui.QLabel('')
            grid.addWidget(l,i, 1)
            self.labels2[port] = l
            socket = self.context.socket(zmq.SUB)
            socket.setsockopt(zmq.SUBSCRIBE,'')
            socket.connect("tcp://localhost:{}".format(port))
            self.sockets[port] = socket
            thread = RecvThread(socket = socket, port = port)
            thread.newpacket.connect(self.refresh_pos)
            thread.start()
            self.threads[port] = thread
        
        self.timer = QtCore.QTimer(interval = 1000)
        self.timer.timeout.connect(self.refresh_sr)
        self.timer.start()
    
    def refresh_pos(self, port, pos):
        self.labels[port].setText('Port {} : Abs pos {}'.format(port, pos))
    
    def refresh_sr(self):
        for port, stream in self.streamhandler.streams.items():
            sr = self.timestampserver.estimate_sampling_rate(port)
            self.labels2[port].setText('{} hz'.format(sr))

# Modify from https://gist.github.com/traviscline/828606
def mainloop(app):
    """
    This loop is necessary for mixing Qt4 and gevent.
    """
    def process_all():
        app.processEvents()
        while app.hasPendingEvents():
            app.processEvents()
            gevent.sleep()
    while True:
        a = gevent.spawn_later(.02, process_all)
        a.join()
    

def main():
    streamhandler = StreamHandler()
    timestampserver = TimestampServer()
    devices = [ ]
    for i in range(nb_devices):
        dev = FakeMultiSignals(streamhandler = streamhandler)
        sampling_rate = sampling_rates[i%4]
        packet_size = packet_sizes[i%4]
        dev.configure( name = 'device {}'.format(i),
                                    nb_channel = 2,
                                    sampling_rate =sampling_rate,
                                    buffer_length = 10.  * (sampling_rate//packet_size)/(sampling_rate/packet_size),
                                    packet_size = packet_size,
                                    )
        dev.initialize()
        devices.append(dev)
    
    
    app = QtGui.QApplication([])
    w1=ControlStartSop(devices = devices, streamhandler= streamhandler, timestampserver = timestampserver)
    w1.show()
    w2=PlotRecvPacket( streamhandler= streamhandler, timestampserver = timestampserver)
    w2.show()
    mainloop(app)
    

if __name__ == "__main__":
    main()