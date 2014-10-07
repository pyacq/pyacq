# -*- coding: utf-8 -*-
"""

"""

import multiprocessing as mp
import numpy as np
import msgpack

from PyQt4 import QtCore,QtGui

import threading

import zmq

import time



#~ class ProcessingBase( QtCore.QObject):
    #~ def __init__(self, stream, streamhandler = None, parent = None):
        #~ QtCore.QObject.__init__(self, parent)
        
        #~ self.stream = stream
        #~ self.streamhandler = streamhandler
        #~ self.context = zmq.Context()
        
        #~ self.in_array = self.stream['shared_array'].to_numpy_array()
        #~ self.half_size = self.in_array.shape[1]/2
        
        #~ self.running = False
        
    #~ def start(self):
        #~ self.running = True
        #~ self.thread = threading.Thread(target = self.loop)
        #~ self.thread.start()
    
    #~ def stop(self, join = True):
        #~ self.running =False
        #~ if join:
            #~ self.thread.join()



class ProcessingBase(QtCore.QThread):
    def __init__(self, stream, streamhandler = None, parent = None):
        QtCore.QThread.__init__(self, parent)
        
        self.stream = stream
        self.streamhandler = streamhandler
        self.context = zmq.Context()
        
        self.in_array = self.stream['shared_array'].to_numpy_array()
        self.half_size = self.in_array.shape[1]/2
        
        self.running = False
        
    def start(self):
        self.running = True
        QtCore.QThread.start(self)
        #~ self.thread = threading.Thread(target = self.loop)
        #~ self.thread.start()
    
    def stop(self, join = True):
        self.running =False
        if join:
            self.thread.join()
    
    def run(self):
        pass
    
    
    


