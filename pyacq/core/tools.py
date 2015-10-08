from pyqtgraph.Qt import QtCore, QtGui
from pyqtgraph.util.mutex import Mutex
import weakref
import numpy as np


class ThreadPollInput(QtCore.QThread):
    """
    Thread that pool in backgroup an InputStream (zmq.SUB).
    And emit Signal.
    Util for Node that have inputs.    
    """
    new_data = QtCore.Signal(int,object)
    def __init__(self, input_stream, timeout = 200, parent = None):
        QtCore.QThread.__init__(self, parent)
        self.input_stream = weakref.ref(input_stream)
        self.timeout = timeout
        
        self.running = False
        self.lock = Mutex()
    
    def run(self):
        with self.lock:
            self.running = True
        
        while True:
            with self.lock:
                if not self.running:
                    break
            
            ev = self.input_stream().poll(timeout = self.timeout)
            if ev>0:
                pos, data = self.input_stream().recv()
                self.new_data.emit(pos, data)

    def stop(self):
        with self.lock:
            self.running = False
