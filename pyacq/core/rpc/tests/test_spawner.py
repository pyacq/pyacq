# -*- coding: utf-8 -*-
# Copyright (c) 2016, French National Center for Scientific Research (CNRS)
# Distributed under the (new) BSD License. See LICENSE for more info.

from pyacq.core.rpc import ProcessSpawner
import os


def test_spawner():
    proc = ProcessSpawner()
    cli = proc.client
    
    # check spawned RPC server has a different PID
    ros = cli._import('os')
    assert os.getpid() != ros.getpid()
    
    # test closing nicely
    proc.stop()
    
    
    # start process with QtRPCServer
    proc = ProcessSpawner(qt=True)
    cli = proc.client

    rqt = cli._import('pyqtgraph.Qt')
    assert rqt.QtWidgets.QApplication.instance() is not None

    # test closing Qt process
    proc.stop()
    