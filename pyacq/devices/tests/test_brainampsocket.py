import time

from pyacq import create_manager
from pyacq.devices.brainampsocket import BrainAmpSocket

from pyqtgraph.Qt import QtCore, QtGui

import pytest

@pytest.mark.skipif(False, reason = 'Need brainamp device to test')
def test_brainampsocket():
    # in main App
    app = QtGui.QApplication([])
    
    dev = BrainAmpSocket()
    #~ dev.configure(brainamp_host = '194.167.217.129', brainamp_port = 51244)
    dev.configure(brainamp_host = '194.167.217.84', brainamp_port = 51244)
    dev.outputs['signals'].configure(protocol = 'tcp', interface = '127.0.0.1',transfertmode = 'plaindata',)
    dev.outputs['triggers'].configure(protocol = 'tcp', interface = '127.0.0.1',transfertmode = 'plaindata',)
    dev.initialize()
    
    #~ viewer = ImageViewer()
    #~ viewer.configure()
    #~ viewer.input.connect(dev.output)
    #~ viewer.initialize()
    #~ viewer.show()
    
    dev.start()
    #~ viewer.start()
    
    def terminate():
        #~ viewer.stop()
        dev.stop()
        #~ viewer.close()
        dev.close()
        app.quit()
    
    # start for a while
    timer = QtCore.QTimer(singleShot = True, interval = 15000)
    timer.timeout.connect(terminate)
    timer.start()
    app.exec_()

if __name__ == '__main__':
    test_brainampsocket()
