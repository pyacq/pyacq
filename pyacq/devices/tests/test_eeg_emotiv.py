# -*- coding: utf-8 -*-
# Copyright (c) 2016, French National Center for Scientific Research (CNRS)
# Distributed under the (new) BSD License. See LICENSE for more info.

import time
import pytest

from pyacq.devices.eeg_emotiv import Emotiv, HAVE_PYCRYPTO
from pyacq.viewers.qoscilloscope import QOscilloscope
from pyqtgraph.Qt import QtCore, QtGui
import pyqtgraph as pg

from collections import OrderedDict
import os

import platform
WINDOWS = (platform.system() == "Windows")
if WINDOWS: 
    try:
        import pywinusb.hid as hid
        HAVE_PYWINUSB = True
    except ImportError:
        HAVE_PYWINUSB = False

# Manual scan of devices
def get_available_devices():
    devices = []
    if WINDOWS:
        try:
            for device in hid.find_all_hid_devices():
                if device.product_name == 'Emotiv RAW DATA':
                    devices.append(device.device_path)
        finally:
            pass
    else:
        serials = {}
        for name in os.listdir("/sys/class/hidraw"):
            realInputPath = os.path.realpath("/sys/class/hidraw/" + name)
            path = '/'.join(realInputPath.split('/')[:-4])
            try:
                with open(path + "/manufacturer", 'r') as f:
                    manufacturer = f.readline()
                if "emotiv" in manufacturer.lower():
                    with open(path + "/serial", 'r') as f:
                        serial = f.readline().strip()
                        if serial not in serials:
                            serials[serial] = []
                        serials[serial].append(name)
            except IOError as e:
                print("Couldn't open file: %s" % e)

        for serial, names in serials.items():
            device_path = '/dev/'+names[1]
            devices.append(device_path)

    return devices

@pytest.mark.skipif(WINDOWS and not HAVE_PYWINUSB, reason='no have pywinusb')
@pytest.mark.skipif(not HAVE_PYCRYPTO, reason='no have pycrypto')
def test_eeg_emotiv_direct():
    # Look for emotiv usb device
    all_devices = get_available_devices()
    device_handle = all_devices[0]
    
    # in main App
    app = pg.mkQApp()
    dev = Emotiv(name='Emotiv0')
    dev.configure(device_handle=device_handle)
    dev.outputs['signals'].configure(
        protocol='tcp', interface='127.0.0.1', transfermode='plaindata',)
    dev.outputs['impedances'].configure(
        protocol='tcp', interface='127.0.0.1', transfermode='plaindata',)
    dev.outputs['gyro'].configure(
        protocol='tcp', interface='127.0.0.1', transfermode='plaindata',)
    dev.initialize()
    viewer = QOscilloscope()
    viewer.configure(with_user_dialog=True)
    viewer.input.connect(dev.outputs['signals'])
    viewer.initialize()
    viewer.show()

    dev.start()
    viewer.start()

    def terminate():
        dev.stop()
        app.quit()

    # start for a while
    timer = QtCore.QTimer(singleShot=True, interval=3000)
    timer.timeout.connect(terminate)
    #~ timer.start()

    app.exec_()


if __name__ == '__main__':

    test_eeg_emotiv_direct()
