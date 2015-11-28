import logging
from pyqtgraph.Qt import QtCore, QtGui


Stylesheet = """
    body {color: #000; font-family: sans;}
    .entry {}
    .error .message {color: #900}
    .warning .message {color: #740}
    .user .message {color: #009}
    .status .message {color: #090}
    .logExtra {margin-left: 40px;}
    .traceback {color: #555; height: 0px;}
    .timestamp {color: #000;}
"""


class LogViewer(QtGui.QWidget):
    """QWidget for displaying and filtering log messages.
    """
    def __init__(self, logger='', parent=None):
        QtGui.QWidget.__init__(self, parent=parent)
        
        # Set up handler to send log records to this widget by signal
        self.handler = QtLogHandler()
        self.handler.new_record.connect(self.new_record)
        if isinstance(logger, str):
            logger = logging.getLogger(logger)
        logger.addHandler(self.handler)
        
        # Set up GUI
        self.layout = QtGui.QGridLayout()
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(self.layout)
        self.text = QtGui.QTextBrowser()
        self.text.document().setDefaultStyleSheet(Stylesheet)
        
    def new_record(self, rec):
        print("NEW LOG RECORD:", rec)
        
        

class QtLogHandler(logging.Handler, QtCore.QObject):
    """Log handler that emits a Qt signal for each record.
    """
    new_record = QtCore.Signal(object)
    
    def __init__(self):
        logging.Handler.__init__(self)
        QtCore.QObject.__init__(self)
        
    def handle(self, record):
        new_record.emit(record)