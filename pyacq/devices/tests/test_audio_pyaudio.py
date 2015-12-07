import time
import pytest
import numpy as np

from pyacq import create_manager
from pyacq.devices.audio_pyaudio import PyAudio, HAVE_PYAUDIO

from pyqtgraph.Qt import QtCore, QtGui
import pyqtgraph as pg


@pytest.mark.skipif(not HAVE_PYAUDIO, reason='no have pyaudio')
def test_local_app_in_out():
    # connect Node.output to Node.input
    # so copy inaudio buffer to out audio buffer
    
    app = pg.mkQApp()
    
    dev = PyAudio()
    dev.configure(nb_channel=2, sample_rate=44100.,
                    input_device_index=0, output_device_index=0,
                    format='int16', chunksize=1024)
    dev.output.configure(protocol='tcp', interface='127.0.0.1', transfertmode='plaindata')
    dev.input.connect(dev.output)
    dev.initialize()
    dev.start()
    
    def terminate():
        dev.stop()
        dev.close()
        app.quit()
    
    # start for a while
    timer = QtCore.QTimer(singleShot=True, interval=3000)
    timer.timeout.connect(terminate)
    timer.start()
    app.exec_()


@pytest.mark.skipif(not HAVE_PYAUDIO, reason='no have pyaudio')
def test_play_sinus():
    # play a buffer to audio out
    
    sr = 44100.
    nb_channel = 2
    chunksize = 4096
    
    man = create_manager(auto_close_at_exit=False)
    nodegroup = man.create_nodegroup()
    
    audioin = nodegroup.create_node('NumpyDeviceBuffer', name='audioin')
    audioout = nodegroup.create_node('PyAudio', name='audioout')
    
    audioin.configure(sample_interval=1./sr, chunksize=chunksize, nb_channel=nb_channel)
    audioin.output.configure(protocol='inproc', transfertmode='plaindata')
    audioin.initialize()
    
    audioout.configure(nb_channel=nb_channel, sample_rate=sr,
                    input_device_index=None, output_device_index=0,
                    format='float32', chunksize=chunksize)
    audioout.input.connect(audioin.output)
    audioout.initialize()
    
    audioout.start()
    audioin.start()
    
    time.sleep(2.)
    
    man.close()


    
if __name__ == '__main__':
    test_local_app_in_out()
    test_play_sinus()

 
