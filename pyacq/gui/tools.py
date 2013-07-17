# -*- coding: utf-8 -*-

from PyQt4 import QtCore,QtGui
import zmq
import msgpack


class RecvPosThread(QtCore.QThread):
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
