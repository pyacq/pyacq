# -*- coding: utf-8 -*-
# Copyright (c) 2016, French National Center for Scientific Research (CNRS)
# Distributed under the (new) BSD License. See LICENSE for more info.

from pyqtgraph.Qt import QtCore, QtGui

import time

import pyacq
from pyacq.viewers import QOscilloscope
from pyacq import create_manager
from pyacq.devices.mcs_w2100 import MultiChannelSystemW2100, download_dll

import pytest


def test_download_dll():
    url_path = download_dll()
    print(url_path)


@pytest.mark.skipif(True, reason='Need MSC device for test')
def test_MultiChannelSystemW2100():
    # in main App
    app = QtGui.QApplication([])
    
    dev = MultiChannelSystemW2100()
    dev.configure(dll_path=None,
                heastage_channel_selection=True, ifb_channel_selection=True, 
                use_digital_channel=True, sample_rate=2000.)
    for name, output in dev.outputs.items():
        dev.outputs[name].configure(protocol='tcp', interface='127.0.0.1',transfermode='plaindata',)
    dev.initialize()
    
    viewers = []
    for name, output in dev.outputs.items():
        viewer = QOscilloscope()
        viewer.configure()
        viewer.input.connect(dev.outputs[name])
        viewer.initialize()
        viewer.show()
        viewers.append(viewer)
    
    dev.start()
    for viewer in viewers:
        viewer.start()
    
    def terminate():
        for viewer in viewers:
            viewer.stop()
            viewer.close()
        
        dev.stop()
        dev.close()
        app.quit()
    
    # start for a while
    timer = QtCore.QTimer(singleShot=True, interval=5000)
    timer.timeout.connect(terminate)
    timer.start()
    
    app.exec_()

if __name__ == '__main__':
    #~ test_download_dll()
    test_MultiChannelSystemW2100()
