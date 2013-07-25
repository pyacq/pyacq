# -*- coding: utf-8 -*-


from .fakemultisignals import FakeMultiSignals

try:
    from .measurementcomputing import MeasurementComputingMultiSignals
except :
    pass


try:
    from .emotiv import EmotivMultiSignals
except :
    pass