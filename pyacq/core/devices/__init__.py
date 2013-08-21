# -*- coding: utf-8 -*-


from .fakedevices import FakeMultiSignals, FakeDigital

try:
    from .measurementcomputing import MeasurementComputingMultiSignals
except :
    pass

try:
    from .comedidevices import ComediMultiSignals
except :
    pass


try:
    from .emotiv import EmotivMultiSignals
except :
    pass