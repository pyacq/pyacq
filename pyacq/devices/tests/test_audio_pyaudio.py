import time
import pytest

from pyacq import create_manager
from pyacq.devices.audio_pyaudio import PyAudio, HAVE_PYAUDIO

from pyqtgraph.Qt import QtCore, QtGui
import pyqtgraph as pg


#~ import logging
#~ logging.getLogger().level=logging.INFO



@pytest.mark.skipif(not HAVE_PYAUDIO, reason = 'no have pyaudio')
def test_local_app_in_out():
    app = pg.mkQApp()
    
    dev  = PyAudio()
    dev.configure(nb_channel = 2, sampling_rate =44100.,
                    input_device_index = 0, output_device_index = 0,
                    format = 'int16', chunksize = 1024)
    
    dev.output.configure(protocol = 'tcp', interface = '127.0.0.1', transfertmode = 'plaindata')
    print(dev.inputs)
    dev.input.connect(dev.output)
    dev.initialize()
    
    dev.start()
    
    def terminate():
        dev.stop()
        app.quit()
    
    # start for a while
    timer = QtCore.QTimer(singleShot = True, interval = 3000)
    timer.timeout.connect(terminate)
    timer.start()
    app.exec_()

    
if __name__ == '__main__':
    test_local_app_in_out()

 
