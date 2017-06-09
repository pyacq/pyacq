# -*- coding: utf-8 -*-
# Copyright (c) 2016, French National Center for Scientific Research (CNRS)
# Distributed under the (new) BSD License. See LICENSE for more info.

import logging
import weakref
import time
import pyqtgraph as pg
from collections import OrderedDict
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
        self.threads = OrderedDict()
        self.thread_order = {}
        
        # Set up GUI
        self.layout = QtGui.QGridLayout()
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(self.layout)
        
        self.tree = QtGui.QTreeWidget()
        self.tree.setWordWrap(True)
        self.tree.setUniformRowHeights(False)
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
        
        self.resize(1200, 800)
        
        self.col_per_thread_toggled(False)
        
    def new_record(self, rec):
        self.last_rec = rec
        self.log_records.append(rec)
        item = LogRecordItem(self, rec)
        i = self.tree.topLevelItemCount() - 1
        if i < 0 or rec.created >= self.tree.topLevelItem(i).rec.created:
            self.tree.addTopLevelItem(item)
        else:
            while i > 0 and rec.created < self.tree.topLevelItem(i-1).rec.created:
                i -= 1
            self.tree.insertTopLevelItem(i, item)
            
        key = item.source_key()
        if key not in self.threads:
            self.threads[key] = item.thread_name()
            self.thread_order[key] = len(self.thread_order)
        
        item.set_col_per_thread(self.col_per_thread_check.isChecked(), self.thread_order)
        
    def get_thread_color(self, key):
        color = self.thread_colors.get(key, None)
        if color is None:
            color = _thread_color_list[len(self.thread_colors) % len(_thread_color_list)]
            self.thread_colors[key] = color
        return color

    def col_per_thread_toggled(self, cpt):
        if cpt:
            self.tree.setColumnCount(len(self.threads) + 1)
            self.tree.setHeaderHidden(False)
            width = max(100, self.tree.width() // self.tree.columnCount())
            for i in range(self.tree.columnCount()):
                self.tree.setColumnWidth(i, width)
            self.tree.setHeaderLabels(['time'] + list(self.threads.values()))
        else:
            self.tree.setColumnCount(3)
            self.tree.setColumnWidth(0, 200)
            self.tree.setColumnWidth(1, 250)
            self.tree.setHeaderHidden(True)
            
        for i in range(self.tree.topLevelItemCount()):
            item = self.tree.topLevelItem(i)
            item.set_col_per_thread(cpt, self.thread_order)

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
        tfrac = '%f'%(rec.created - int(rec.created))
        tfrac = tfrac[tfrac.index('.'):]
        self._date_str = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(rec.created)) + tfrac
        QtGui.QTreeWidgetItem.__init__(self)

    def thread_name(self):
        return self._thread_name

    def source_key(self):
        record = self.rec
        hid = getattr(record, 'hostname', get_host_name())
        pid = getattr(record, 'process_name', get_process_name())
        tid = getattr(record, 'thread_name', get_thread_name(record.thread))
        return (hid, pid, tid)
    
    def set_col_per_thread(self, cpt, order):
        blk = pg.mkBrush('k')
        if cpt is False:
            text = [self._date_str, self._thread_name, self._msg]
            self.setForeground(0, blk)
            self.setForeground(1, pg.mkBrush(self._color))
            self.setForeground(2, blk)
        else:
            col = order[self.source_key()]
            text = [self._date_str] + ([''] * len(order))
            text[col+1] = self._msg
            for i in range(self._logview().tree.columnCount()):
                self.setForeground(i, blk)
            self.setForeground(col+1, pg.mkBrush(self._color))
            
        for i in range(self._logview().tree.columnCount()):
            self.setTextAlignment(i, QtCore.Qt.AlignLeft | QtCore.Qt.AlignTop)
            self.setText(i, text[i])


class QtLogHandler(logging.Handler, QtCore.QObject):
    """Log handler that emits a Qt signal for each record.
    """
    new_record = QtCore.Signal(object)
    
    def __init__(self):
        logging.Handler.__init__(self)
        QtCore.QObject.__init__(self)
        
    def handle(self, record):
        self.new_record.emit(record)
