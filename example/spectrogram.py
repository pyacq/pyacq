"""
Generate random analog signals and display them in a QOscilloscope node.
"""
from pyacq import Spectrogram, FakeSpectralSource
from pyqtgraph.Qt import QtCore, QtGui

app = QtGui.QApplication([])

source = FakeSpectralSource(nb_channel=None, chunksize=32)

viewer = Spectrogram()
viewer.configure()
viewer.input.connect(source.output)

source.start()
viewer.start()

viewer.show()
#app.exec_()

