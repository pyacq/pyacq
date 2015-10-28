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


class LogWidget(QtGui.QWidget):
    def __init__(self, parent=None):
        QtGui.QWidget.__init__(self, parent=parent)
        self.layout = QtGui.QGridLayout()
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(self.layout)
        self.tab_widget = QtGui.QTabWidget()
        self.layout.addWidget(self.tab_widget, 0, 0)
        
        self.tabs = {}
        
    def message(self, sender, message):
        if sender not in self.tabs:
            text = QtGui.QTextBrowser()
            self.tab_widget.addTab(text, sender)
            self.tabs[sender] = text
            
            text.document().setDefaultStyleSheet(Stylesheet)
            
        text = self.tabs[sender]
        
        text.append(message)
        

#class LogThread(QtCore.QThread):
    
    #new_message = QtCore.QSignal(object, object)  # sender, message
    
    #def __init__(self, widget):
        #QtCore.QThread.__init__(self)
        #self.server = RPCServer()
        #self.server['logger'] = self
        #self.client = RPCClient(self.server.address)
        #self.logger = self.client['logger']
        
    #def run(self):
        #self.server.run_forever()
        
    #def message(self, sender, message):
        #self.new_message.emit(sender, message)

