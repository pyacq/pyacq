# -*- coding: utf-8 -*-
# Copyright (c) 2016, French National Center for Scientific Research (CNRS)
# Distributed under the (new) BSD License. See LICENSE for more info.

import logging
import weakref
import pyqtgraph as pg
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
    thread_colors = {}

    def __init__(self, logger='', parent=None):
        QtGui.QWidget.__init__(self, parent=parent)
        
        # Set up handler to send log records to this widget by signal
        self.handler = QtLogHandler()
        self.handler.new_record.connect(self.new_record)
        if isinstance(logger, str):
            logger = logging.getLogger(logger)
        logger.addHandler(self.handler)

        self.log_records = []
        
        # Set up GUI
        self.layout = QtGui.QGridLayout()
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(self.layout)
        
        self.tree = QtGui.QTreeWidget()
        self.tree.setWordWrap(True)
        self.tree.setUniformRowHeights(False)
        self.tree.setColumnWidth(0, 250)
        self.tree.setColumnCount(2)
        self.tree.setHeaderHidden(True)
        self.layout.addWidget(self.tree, 0, 0)
        
        self.ctrl = QtGui.QWidget()
        self.layout.addWidget(self.ctrl, 0, 1)
        
        self.ctrl_layout = QtGui.QGridLayout()
        self.ctrl.setLayout(self.ctrl_layout)
        
        self.col_per_thread_check = QtGui.QCheckBox("col per thread")
        self.ctrl_layout.addWidget(self.col_per_thread_check, 0, 0)
        
        self.multiline_check = QtGui.QCheckBox("multiline")
        self.ctrl_layout.addWidget(self.multiline_check, 1, 0)
        
        self.col_per_thread_check.toggled.connect(self.col_per_thread_toggled)
        self.multiline_check.toggled.connect(self.multiline_toggled)
        
        self.resize(800, 600)
        
    def new_record(self, rec):
        self.last_rec = rec
        self.log_records.append(rec)
        item = LogRecordItem(self, rec)
        self.tree.addTopLevelItem(item)
        #header = self.get_thread_header(rec)
        #self.text.append("%s %s\n" % (header, rec.getMessage()))
        
    def get_thread_color(self, key):
        color = self.thread_colors.get(key, None)
        if color is None:
            color = _thread_color_list[len(self.thread_colors) % len(_thread_color_list)]
            self.thread_colors[key] = color
        return color

    def col_per_thread_toggled(self, cpt):
        pass

    def multiline_toggled(self, ml):
        pass


class LogRecordItem(QtGui.QTreeWidgetItem):
    def __init__(self, logview, rec):
        self.rec = rec
        self._logview = weakref.ref(logview)
        key = self.source_key()
        self._color = logview.get_thread_color(key)
        self._msg = rec.getMessage()
        self._thread_name = "%s : %s : %s" % key
        QtGui.QTreeWidgetItem.__init__(self, [self._thread_name, self._msg])
        self.setTextAlignment(0, QtCore.Qt.AlignLeft | QtCore.Qt.AlignTop)
        self.setForeground(0, pg.mkBrush(self._color))

    def source_key(self):
        record = self.rec
        hid = getattr(record, 'hostname', get_host_name())
        pid = getattr(record, 'process_name', get_process_name())
        tid = getattr(record, 'thread_name', get_thread_name(record.thread))
        return (hid, pid, tid)
        

class QtLogHandler(logging.Handler, QtCore.QObject):
    """Log handler that emits a Qt signal for each record.
    """
    new_record = QtCore.Signal(object)
    
    def __init__(self):
        logging.Handler.__init__(self)
        QtCore.QObject.__init__(self)
        
    def handle(self, record):
        self.new_record.emit(record)
