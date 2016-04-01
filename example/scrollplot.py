"""
Simulate a multi-electrode array and stream the data to a grid of scrolling plots.
"""
from pyacq import ScrollPlot, FakeSpikeSource
from pyqtgraph.Qt import QtCore, QtGui

app = QtGui.QApplication([])

# simulate a 10x10 electrode array
source = FakeSpikeSource(nb_channel=(10, 10), chunksize=512)

viewer = ScrollPlot()
viewer.configure()
viewer.input.connect(source.output)

source.start()
viewer.start()

viewer.show()
app.exec_()

