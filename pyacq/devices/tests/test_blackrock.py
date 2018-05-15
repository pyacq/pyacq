# -*- coding: utf-8 -*-
# Copyright (c) 2016, French National Center for Scientific Research (CNRS)
# Distributed under the (new) BSD License. See LICENSE for more info.

import time

from pyacq import create_manager
from pyacq.devices.blackrock import Blackrock, HAVE_BLACKROCK


from pyqtgraph.Qt import QtCore, QtGui

import pytest


@pytest.mark.skipif(not HAVE_BLACKROCK, reason='no have blackrock')
def test_blackrock():
    # in main App
    app = QtGui.QApplication([])

    dev = Blackrock()
    dev.configure()
    dev.outputs['aichannels'].configure(protocol='tcp', interface='127.0.0.1', transfertmode='plaindata')
    dev.initialize()
    dev.start()
    
    global n
    n = 0
    
    def terminate():
        global n
        
        print('stop', n)
        dev.stop()
        if n<3:
            n += 1
            print('start', n)
            dev.start()
        else:
            print('terminate')
            app.quit()
    
    # start  and stop 3 times
    timer = QtCore.QTimer(singleShot=False, interval=1000)
    timer.timeout.connect(terminate)
    timer.start()

    app.exec_()

if __name__ == '__main__':
    test_ni_daqmx()
