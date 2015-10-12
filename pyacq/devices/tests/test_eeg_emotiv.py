import time
import pytest

from pyacq.devices.eeg_emotiv import Emotiv, HAVE_PYCRYPTO#, HAVE_PYWINUSB
from pyacq.viewers.qoscilloscope  import QOscilloscope
from pyqtgraph.Qt import QtCore, QtGui

from collections import OrderedDict
import os 



#Manual scan of devices
def get_available_devices():
    serials = OrderedDict()
    for name in os.listdir("/sys/class/hidraw"):
        real_input_path =  os.path.realpath("/sys/class/hidraw/" + name)
        path = '/'.join(real_input_path.split('/')[:-4])
        try:
            with open(path + "/manufacturer", 'r') as f:
                manufacturer = f.readline()
            if "emotiv" in manufacturer.lower():
                with open(path + "/serial", 'r') as f:
                    serial = f.readline().strip()
                    if serial not in serials:
                        serials[serial] = [ ]
                    serials[serial].append(name)
        except IOError as e:
            print("Couldn't open file: %s"% e)
    
    all_device_path = []
    for serial, names in serials.items():
        device_path = '/dev/'+names[1]
        all_device_path.append(device_path)
    
    return all_device_path




#~ @pytest.mark.skipif(not HAVE_PYWINUSB, reason = 'no have pywinusb')
@pytest.mark.skipif(not HAVE_PYCRYPTO, reason = 'no have pycrypto')
def test_eeg_emotiv_direct():
    
    #Look for emotiv usb device
    all_device_path = get_available_devices()
    device_path = all_device_path[0]
    
    # in main App
    app = QtGui.QApplication([])
    dev = Emotiv(name = 'Emotiv0')
    dev.configure(device_path = device_path)
    dev.outputs['signals'].configure(protocol = 'tcp', interface = '127.0.0.1',transfermode = 'plaindata',)
    dev.outputs['impedances'].configure(protocol = 'tcp', interface = '127.0.0.1',transfermode = 'plaindata',)
    dev.outputs['gyro'].configure(protocol = 'tcp', interface = '127.0.0.1',transfermode = 'plaindata',)
    dev.initialize()
    
    
    viewer = QOscilloscope()
    viewer.configure(with_user_dialog = True)
    viewer.input.connect(dev.outputs['signals'])
    viewer.initialize()
    viewer.show()
    
    dev.start()
    viewer.start()


    def terminate():
        dev.stop()
        app.quit()
    
    # start for a while
    timer = QtCore.QTimer(singleShot = True, interval = 3000)
    timer.timeout.connect(terminate)
    timer.start()
    
    app.exec_()
    
    
    
    

if __name__ == '__main__':
    
    test_eeg_emotiv_direct()
    
