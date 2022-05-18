# -*- coding: utf-8 -*-
# Copyright (c) 2016, French National Center for Scientific Research (CNRS)
# Distributed under the (new) BSD License. See LICENSE for more info.

import pytest

from pyacq.core import Node
from pyacq.viewers.imageviewer import ImageViewer
from pyacq.devices import NumpyDeviceBuffer
import numpy as np

from pyqtgraph.Qt import QtCore, QtGui
import pyqtgraph as pg


sample_rate = 10

num_video = 3


class FakeCamera(Node):
    _output_specs = {'video': dict(streamtype='analogsignal', 
                                                shape=(720, 600, 3), compression ='', sample_rate =5,
                                                dtype='uint8'
                                                )}
    def __init__(self, **kargs):
        Node.__init__(self, **kargs)

    def _configure(self, buffer=None, sample_rate=5):
        self.sample_rate = sample_rate
        self.output.spec['sample_rate'] = sample_rate
        self.buffer = buffer
        
    def _initialize(self):
        self.head = 0
        interval = int(1000 / self.sample_rate)
        self.timer = QtCore.QTimer(singleShot=False, interval=interval)
        self.timer.timeout.connect(self.send_data)
    
    def _start(self):
        self.head = 0
        self.timer.start()

    def _stop(self):
        self.timer.stop()
    
    def _close(self):
        self.buffer = None
    
    def send_data(self):
        self.output.send(self.buffer[self.head, :, :, :], index=self.head)
        self.head += 1
        self.head = self.head % self.buffer.shape[0]
        



def test_imageviewer():
    
    app = pg.mkQApp()
    
    cameras = []
    for i in range(num_video):
        buffer = np.random.randint(0, high=255, size=(10, 600, 720, 3), dtype='uint8')
        buffer[:, :, :, i%3] = 255

        camera = FakeCamera()
        camera.configure(buffer=buffer, sample_rate=5)
        camera.output.configure(protocol='tcp', interface='127.0.0.1', transfermode='plaindata')
        camera.initialize()
        cameras.append(camera)
    
    viewers = []
    for i in range(num_video):
        viewer = ImageViewer()
        viewer.configure()
        viewer.input.connect(cameras[i].output)
        viewer.initialize()
        viewer.show()
        viewers.append(viewer)
    
    multi = ImageViewer()
    multi.configure(num_video=num_video, nb_column=2)
    for i in range(num_video):
        multi.inputs[f'video{i}'].connect(cameras[i].output)
    multi.initialize()
    multi.show()
    
    
    def terminate():

        for i in range(num_video):
            cameras[i].stop()

        for i in range(num_video):
            viewers[i].stop()

        for i in range(num_video):
            viewers[i].close()
        
        for i in range(num_video):
            cameras[i].close()
        
        multi.stop()
        multi.close()
        
        app.quit()
    
    for i in range(num_video):
        cameras[i].start()
        viewers[i].start()
    
    multi.start()
    
    # start for a while
    timer = QtCore.QTimer(singleShot=True, interval=2000)
    timer.timeout.connect(terminate)
    timer.start()
    
    app.exec_()


  

if __name__ == '__main__':
    test_imageviewer()
