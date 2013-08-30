# -*- coding: utf-8 -*-
"""
Device list
"""

from pyacq import StreamHandler, ComediMultiSignals


def test1():
    
    for name, info_device in ComediMultiSignals.get_available_devices().items():
        print name
        print info_device
    



if __name__ == '__main__':
    test1()
