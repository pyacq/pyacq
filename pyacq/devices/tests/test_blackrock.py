# -*- coding: utf-8 -*-
# Copyright (c) 2016, French National Center for Scientific Research (CNRS)
# Distributed under the (new) BSD License. See LICENSE for more info.

import time

from pyacq import create_manager
from pyacq.devices.blackrock import Blackrock, open_sbSdk_dll, cbSdkConnection, CbSdkError
from pyacq.viewers import QOscilloscope

from pyqtgraph.Qt import QtCore, QtWidgets

import pytest


@pytest.mark.skip(reason="need Device")
def test_open_sbSdk_dll():
    #~ cbSdk = open_sbSdk_dll(dll_path='c:/')
    #~ assert cbSdk is None
    
    cbSdk = open_sbSdk_dll(dll_path=None)
    nInstance=0
    nInPort=51002
    nOutPort=51001
    nRecBufSize=4096*2048
    szInIP=b"192.168.137.1"
    szOutIP=b"192.168.137.128"
    
    con = cbSdkConnection(nInPort, nOutPort,nRecBufSize, 0,
                        szInIP, szOutIP)
    cbSdk.Open(0, 0, con)
    cbSdk.Close(0)
    with pytest.raises(CbSdkError):
        cbSdk.Close(0)
    


@pytest.mark.skip(reason="need Device")
def test_blackrock():
    #~ ai_channels = [1, ]
    ai_channels = [1,2,3, 4, 10, 11, 12, 13]
    #~ ai_channels = list(range(16, 25))
    #~ ai_channels = [20, 21, 22, 23]
    #~ ai_channels = [1, 2, 3, 4, 5, 6, 7, 8, 
                #~ 17, 18, 19, 20, 21, 22, 23, 24, 
                #~ 33, 34, 35, 36, 37, 38, 39, 40,
                #~ 49, 50, 51, 52, 53, 54, 55, 56,
                #~ 129,
                #~ ]
    

    # in main App
    app = QtWidgets.QApplication([])
    
    # for testing in background
    #~ man = create_manager(auto_close_at_exit=True)
    #~ ng0 = man.create_nodegroup()
    #~ dev = ng0.create_node('Blackrock')
    
    # tested in local Node
    dev = Blackrock()
    
    # dev.configure(nInstance=0,szInIP=b"192.168.137.1", ai_channels=ai_channels, apply_config=True)
    dev.configure(nInstance=0, connection_type='central', ai_channels=ai_channels,  apply_config=False)
    
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
    viewer.params['refresh_interval'] = 100
    
    
    dev.start()
    viewer.start()
    
    def terminate():
        global n
        
        print('stop', n)
        dev.stop()
        viewer.stop()
        print('stop OK', n)
        if n<3:
            n += 1
            print('start', n)
            dev.start()
            viewer.start()
            print('start OK', n)
        else:
            print('terminate')
            dev.close()
            viewer.close()
            app.quit()
    
    # start  and stop 3 times
    timer = QtCore.QTimer(singleShot=False, interval=1000)
    timer.timeout.connect(terminate)
    timer.start()

    app.exec_()

if __name__ == '__main__':
    test_open_sbSdk_dll()
    test_blackrock()

