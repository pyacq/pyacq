import time
import pytest

from pyacq.devices.eeg_emotiv import Emotiv, HAVE_PYCRYPTO#, HAVE_PYWINUSB
from pyacq.viewers.imageviewer import ImageViewer
from pyqtgraph.Qt import QtCore, QtGui

from collections import OrderedDict
import os 



#Manual scan of devices
def get_info(device_path):
    info = { }
    info['class'] = 'EmotivMultiSignals'
    info['path'] = device_path
    
    name = device_path.strip('/dev/')
    realInputPath =  os.path.realpath("/sys/class/hidraw/" + name)
    path = '/'.join(realInputPath.split('/')[:-4])
    with open(path + "/manufacturer", 'r') as f:
        manufacturer = f.readline()
    with open(path + "/serial", 'r') as f:
        serial = f.readline().strip()
    
    info['board_name'] = '{} #{}'.format(manufacturer, serial).replace('\n', '').replace('\r', '')
    info['serial'] = serial
    info['global_params'] = {
                                            'buffer_length' : 60.,
                                            }
    return info

def get_available_devices():
    devices = OrderedDict()
    
    serials = { }
    for name in os.listdir("/sys/class/hidraw"):
        realInputPath =  os.path.realpath("/sys/class/hidraw/" + name)
        path = '/'.join(realInputPath.split('/')[:-4])
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
            print ("Couldn't open file: %s"% e)
    
    for serial, names in serials.items():
        device_path = '/dev/'+names[1]
        info = get_info(device_path)
        devices['Emotiv '+device_path] = info
    
    return devices




#~ @pytest.mark.skipif(not HAVE_PYWINUSB, reason = 'no have pywinusb')
@pytest.mark.skipif(not HAVE_PYCRYPTO, reason = 'no have pycrypto')
def test_eeg_emotiv_direct():
    
    #Look for emotiveusb device
    device_info = []
    devices = get_available_devices()
    device_path= list(devices.values())[0]['path'] 
    device_info = get_info(device_path)
    
    # in main App
    app = QtGui.QApplication([])
    
    dev = Emotiv(name = 'Emotiv0')
    dev.configure(device_info = device_info)
    dev.outputs['signals'].configure(protocol = 'tcp', interface = '127.0.0.1',transfertmode = 'plaindata',)
    dev.outputs['impedances'].configure(protocol = 'tcp', interface = '127.0.0.1',transfertmode = 'plaindata',)
    dev.outputs['gyro'].configure(protocol = 'tcp', interface = '127.0.0.1',transfertmode = 'plaindata',)
    dev.initialize()
    
    viewer = ImageViewer()
    viewer.configure()
    viewer.input.connect(dev.outputs['signals'])
    viewer.initialize()
    viewer.show()
    
    dev.start()
    viewer.start()


    def terminate():
        dev.stop()
        app.quit()
    
    # start for a while
    timer = QtCore.QTimer(singleShot = True, interval = 5000)
    timer.timeout.connect(terminate)
    timer.start()
    app.exec_()
    
    
    
    

if __name__ == '__main__':
    
    test_eeg_emotiv_direct()
    
