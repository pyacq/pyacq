# -*- coding: utf-8 -*-
# Copyright (c) 2016, French National Center for Scientific Research (CNRS)
# Distributed under the (new) BSD License. See LICENSE for more info.

import time

from pyacq import create_manager
from pyacq.devices.blackrock import Blackrock, HAVE_BLACKROCK
from pyacq.viewers import QOscilloscope

from pyqtgraph.Qt import QtCore, QtGui

import pytest


@pytest.mark.skipif(not HAVE_BLACKROCK, reason='no have blackrock')
def test_blackrock():
    ai_channels = [1, ]
    #~ ai_channels = [1,2,3, 4, 10, 11, 12, 13]
    #~ ai_channels = list(range(16, 25))
    #~ ai_channels = [20, 21, 22, 23]
    

    # in main App
    app = QtGui.QApplication([])

    dev = Blackrock()
    dev.configure(ai_channels=ai_channels, chunksize=2*14)
    dev.outputs['aichannels'].configure(protocol='tcp', interface='127.0.0.1', transfertmode='plaindata')
    dev.initialize()
    
    global n
    n = 0


    viewer = QOscilloscope()
    viewer.configure(with_user_dialog=True)
    viewer.input.connect(dev.output)
    viewer.initialize()
    viewer.show()
    viewer.params['scale_mode'] = 'by_channel'
    viewer.params['xsize'] = 1
    
    
    dev.start()
    viewer.start()
    
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
    #~ timer.start()

    app.exec_()

if __name__ == '__main__':
    test_blackrock()
