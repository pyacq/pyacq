# -*- coding: utf-8 -*-
"""
Device list
"""

from pyacq import StreamHandler, EmotivMultiSignals


def test1():

    for name, info_device in EmotivMultiSignals.get_available_devices().items():
        print name
        print info_device




if __name__ == '__main__':
    test1()
