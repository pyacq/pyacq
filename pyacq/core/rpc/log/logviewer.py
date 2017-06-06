# -*- coding: utf-8 -*-
# Copyright (c) 2016, French National Center for Scientific Research (CNRS)
# Distributed under the (new) BSD License. See LICENSE for more info.

import logging
from pyqtgraph.Qt import QtCore, QtGui
from .remote import get_host_name, get_process_name, get_thread_name


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

_thread_color_list = [
    "#AA0000",
    "#00AA00",
    "#0000AA",
    "#888800",
    "#880088",
    "#008888",
]


class LogViewer(QtGui.QWidget):
    """QWidget for displaying and filtering log messages.
    """
    thread_headers = {}

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
        self.layout.addWidget(self.text, 0, 0)
        
        self.resize(800, 600)
        
    def new_record(self, rec):
        self.last_rec = rec
        header = self.get_thread_header(rec)
        self.text.append("%s %s\n" % (header, rec.getMessage()))
        
    def get_thread_header(self, record):
        hid = getattr(record, 'hostname', get_host_name())
        pid = getattr(record, 'process_name', get_process_name())
        tid = getattr(record, 'thread_name', get_thread_name(record.thread))
        key = (hid, pid, tid)
        header = self.thread_headers.get(key, None)
        if header is None:
            header = '[%s:%s:%s]' % (hid, pid, tid)
            color = _thread_color_list[len(self.thread_headers) % len(_thread_color_list)]
            header = '<span style="color: %s;">%s</span>' % (color, header)
            self.thread_headers[key] = header
        return header
        

class QtLogHandler(logging.Handler, QtCore.QObject):
    """Log handler that emits a Qt signal for each record.
    """
    new_record = QtCore.Signal(object)
    
    def __init__(self):
        logging.Handler.__init__(self)
        QtCore.QObject.__init__(self)
        
    def handle(self, record):
        self.new_record.emit(record)
