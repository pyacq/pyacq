# -*- coding: utf-8 -*-
"""
Device list
"""

from pyacq import StreamHandler, MeasurementComputingMultiSignals


def test1():
    
    for name, info_device in MeasurementComputingMultiSignals.get_available_devices().items():
        print name
        print info_device
    



if __name__ == '__main__':
    test1()
