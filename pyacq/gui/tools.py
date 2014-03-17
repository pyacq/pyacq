# -*- coding: utf-8 -*-

from PyQt4 import QtCore,QtGui
import zmq
import msgpack

import numpy as np
import time

class RecvPosThread(QtCore.QThread):
    """
    Thread for reading in loop in a stream to get the current pos.
    """
    newpacket = QtCore.pyqtSignal(int, int)
    def __init__(self, parent=None, socket = None, port=None):
        QtCore.QThread.__init__(self, parent)
        self.running = False
        self.socket = socket
        self.port = port
        self.pos = None
    
    def run(self):
        self.running = True
        while self.running:
            events = self.socket.poll(50)
            if events ==0:
                time.sleep(.05)
                continue
            
            message = self.socket.recv()
            self.pos = msgpack.loads(message)
            self.newpacket.emit(self.port, self.pos)
    
    def stop(self):
        self.running = False

class WaitLimitThread(QtCore.QThread):
    """
    thread for waiting in a stream a pos.
    """
    limit_reached = QtCore.pyqtSignal(int)
    def __init__(self, parent=None, socket = None, pos_limit = None):
        QtCore.QThread.__init__(self, parent)
        self.running = False
        self.socket = socket
        self.pos_limit = pos_limit
    
    def run(self):
        message = self.socket.recv()
        pos = msgpack.loads(message)
        #~ print self.pos_limit-pos
        #

        self.running = True
        while self.running:
            events = self.socket.poll(50)
            if events ==0:
                time.sleep(.05)
                continue
            message = self.socket.recv()
            pos = msgpack.loads(message)
            
            if pos>=self.pos_limit:
                self.limit_reached.emit(self.pos_limit)
                self.running = False
                break
            
    
    def stop(self):
        self.running = False
    
    
        





class MultiChannelParamsSetter:
    """
    For Oscilloscope, OscilloscopeDIgital and TimeFreq.
    Allow external configuration.
    """
    def set_params(self, **kargs):
        pglobal = [ p['name'] for p in self._param_global]
        pchan = [ p['name']+'s' for p in self._param_by_channel]
        nb_channel = self.stream['nb_channel']
        for k, v in kargs.items():
            if k in pglobal:
                self.paramGlobal.param(k).setValue(v)
            elif k in pchan:
                if isinstance(v, np.ndarray):
                    v = v.tolist()
                for channel in range(nb_channel):
                    p  = self.paramChannels.children()[channel]
                    p.param(k[:-1]).setValue(v[channel])
        
    def get_params(self):
        nb_channel = self.stream['nb_channel']
        params = { }
        for p in self._param_global:
            v = self.paramGlobal[p['name']]
            if 'color' in p['name']:
                if type(v) ==  QtGui.QColor:
                    v = str(v.name())
            params[p['name']] = v
        for p in self._param_by_channel:
            values = [ ]
            for channel in range(nb_channel):
                v= self.paramChannels.children()[channel][p['name']]
                if 'color' in p['name']:
                    v = str(v.name())
                values.append(v)
            params[p['name']+'s'] = values
        return params    