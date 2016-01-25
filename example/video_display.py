"""
Generate a random video feed and display it in an ImageViewer node.
"""
from pyacq import ImageViewer, FakeVideoSource
from pyqtgraph.Qt import QtCore, QtGui

app = QtGui.QApplication([])

source = FakeVideoSource()

viewer = ImageViewer()
viewer.configure()
viewer.input.connect(source.output)

source.start()
viewer.start()

viewer.show()
app.exec_()

