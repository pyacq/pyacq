# -*- coding: utf-8 -*-


# 3d plot in pyqtgraph :
# apt-get install python-opengl
# apt-get install python-qt4-gl


from PyQt4 import QtCore,QtGui
import pyqtgraph as pg
import zmq

from .tools import RecvPosThread
from .guiutil import *
from .multichannelparam import MultiChannelParam

import pyqtgraph.opengl as gl


class Topoplot(QtGui.QWidget):
    def __init__(self, stream = None, parent = None,):
        QtGui.QWidget.__init__(self, parent)
        
        assert stream['type'] == 'signals_stream_sharedmem'
        
        self.stream = stream
        
        self.context = zmq.Context()
        self.socket = self.context.socket(zmq.SUB)
        self.socket.setsockopt(zmq.SUBSCRIBE,'')
        self.socket.connect("tcp://localhost:{}".format(self.stream['port']))
        
        self.thread_pos = RecvPosThread(socket = self.socket, port = self.stream['port'])
        self.thread_pos.start()
        
        self.mainlayout = QtGui.QVBoxLayout()
        self.setLayout(self.mainlayout)
        #Animation : compute surface vertex data
        self.w = gl.GLViewWidget()
        self.w.setCameraPosition(distance=30)
        self.mainlayout.addWidget(self.w)
        
        
                # Create parameters
        n = stream['nb_channel']
        self.np_array = self.stream['shared_array'].to_numpy_array()
        self.half_size = self.np_array.shape[1]/2
        sr = self.stream['sampling_rate']
       
        ## Animated example
        ## compute surface vertex data
        cols = 90
        rows = 100
        x = np.linspace(-8, 8, cols+1).reshape(cols+1,1)
        y = np.linspace(-8, 8, rows+1).reshape(1,rows+1)
        d = (x**2 + y**2) * 0.1
        d2 = d ** 0.5 + 0.1
        
        ## precompute height values for all frames
        phi = np.arange(0, np.pi*2, np.pi/20.)
        print phi
        self.z = np.sin(d[np.newaxis,...] + phi.reshape(phi.shape[0], 1, 1)) / d2[np.newaxis,...]

        ## create a surface plot, tell it to use the 'heightColor' shader
        ## since this does not require normal vectors to render (thus we 
        ## can set computeNormals=False to save time when the mesh updates)
        self.p1 = gl.GLSurfacePlotItem(x=x[:,0], y = y[0,:], shader='heightColor', computeNormals=False, smooth=False)
        self.p1.shader()['colorMap'] = np.array([0.2, 2, 0.5, 0.2, 1, 1, 0.2, 0, 2])
        self.w.addItem(self.p1)
        self.index = 1

        self.timer = QtCore.QTimer(interval = 100)
        self.timer.timeout.connect(self.refresh)
        self.timer.start()
        
        
    def refresh(self):
        #global p4, z, index
        z = self.z
        self.index -= 1
        self.p1.setData(z=z[self.index%z.shape[0]])
        print self.np_array[1,self.thread_pos.pos%self.half_size+self.half_size]
            
            