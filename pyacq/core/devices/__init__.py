# -*- coding: utf-8 -*-


from .fakedevices import FakeMultiSignals, FakeDigital
device_classes = [FakeMultiSignals, FakeDigital ]

try:
    from .measurementcomputing import MeasurementComputingMultiSignals
    device_classes += [MeasurementComputingMultiSignals]
except :
    pass

try:
    from .comedidevices import ComediMultiSignals
    device_classes += [ComediMultiSignals]
except :
    pass


try:
    from .emotiv import EmotivMultiSignals
    device_classes += [EmotivMultiSignals]
except :
    pass


