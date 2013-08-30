# -*- coding: utf-8 -*-
"""
Device list
"""

from pyacq import StreamHandler, FakeMultiSignals, FakeDigital


def test1():
    
    for name, info_device in FakeMultiSignals.get_available_devices().items():
        print name
        print info_device
    
def test2():
    
    for name, info_device in FakeDigital.get_available_devices().items():
        print name
        print info_device



if __name__ == '__main__':
    test1()
    test2()
