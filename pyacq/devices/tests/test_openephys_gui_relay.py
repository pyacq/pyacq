# -*- coding: utf-8 -*-
# Copyright (c) 2016, French National Center for Scientific Research (CNRS)
# Distributed under the (new) BSD License. See LICENSE for more info.

import time
from pprint import pprint

import pyacq
from pyacq import create_manager
from pyacq.devices.openephys_gui_relay import OpenEphysGUIRelay
from pyacq.viewers import QOscilloscope

from pyqtgraph.Qt import QtCore, QtGui

import pytest

def test_openephys_gui_relay_nogui():
    app = QtGui.QApplication([])
    
    dev = OpenEphysGUIRelay()
    dev.configure(openephys_url='tcp://127.0.0.1:20000')
    dev.outputs['signals'].configure()
    dev.initialize()
    

    stream_params = dev.outputs['signals'].params
    
    stream = pyacq.InputStream()
    stream.connect(stream_params)
    stream.set_buffer(size=stream_params['buffer_size'])
    
    dev.start()

    # read loop
    for i in range(50):
        pos, data = stream.recv(return_data=True)
        print(pos)
        #~ data = stream.get_data(pos-100, pos)
        print(data.shape, data.dtype)
    
    dev.stop()
    
    
    #~ app.exec_()
    
    


@pytest.mark.skipif(True, reason='Need brainamp device to test')
def test_openephys_gui_relay():
    # in main App
    app = QtGui.QApplication([])
    
    dev = OpenEphysGUIRelay()
    dev.configure(openephys_url='tcp://127.0.0.1:20000')
    dev.outputs['signals'].configure()
    dev.initialize()
    
    pprint(dev.outputs['signals'].params)
    
    viewer = QOscilloscope()
    viewer.configure()
    viewer.input.connect(dev.outputs['signals'].params)
    viewer.initialize()
    viewer.show()
    
    dev.start()
    viewer.start()
    
    def terminate():
        viewer.stop()
        dev.stop()
        viewer.close()
        dev.close()
        app.quit()
    
    # start for a while
    timer = QtCore.QTimer(singleShot=True, interval=5000)
    #~ timer.timeout.connect(terminate)
    #~ timer.start()
    
    app.exec_()

if __name__ == '__main__':
    #~ test_openephys_gui_relay_nogui()
    test_openephys_gui_relay()
