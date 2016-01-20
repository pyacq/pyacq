# -*- coding: utf-8 -*-
# Copyright (c) 2016, French National Center for Scientific Research (CNRS)
# Distributed under the (new) BSD License. See LICENSE for more info.

import time

from pyacq import create_manager
from pyacq.devices.eeg_openBCI import OpenBCI, HAVE_PYSERIAL
from pyacq.viewers import QOscilloscope

from pyqtgraph.Qt import QtCore, QtGui

import pytest

@pytest.mark.skipif(not HAVE_PYSERIAL, reason='no have pyserial')
def test_eeg_OpenBCI():
    # in main App
    app = QtGui.QApplication([])
    
    dev = OpenBCI()
    dev.configure(board_name="Daisy", device_handle='/dev/ttyUSB0', device_baud=115200)
    dev.outputs['chan'].configure(protocol='tcp', interface='127.0.0.1',transfermode='plaindata',)
    dev.outputs['aux'].configure(protocol='tcp', interface='127.0.0.1',transfermode='plaindata',)
    dev.initialize()
    
    viewer = QOscilloscope()
    viewer.configure()
    viewer.input.connect(dev.outputs['chan'])
    viewer.initialize()
    viewer.show()
    
    # dev.print_register_settings()
    dev.start()
    viewer.start()
    
    def terminate():
        viewer.stop()
        dev.stop()
        viewer.close()
        dev.close()
        app.quit()
    
    # start for a while
    timer = QtCore.QTimer(singleShot=True, interval=10000)
    timer.timeout.connect(terminate)
    timer.start()
    
    app.exec_()

if __name__ == '__main__':
    test_eeg_OpenBCI()
