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
        self.layout.addWidget(self.tree, 0, 0)
        
        self.ctrl = QtGui.QWidget()
        self.ctrl.setMaximumWidth(200)
        self.layout.addWidget(self.ctrl, 0, 1)
        
        self.ctrl_layout = QtGui.QGridLayout()
        self.ctrl.setLayout(self.ctrl_layout)

        self.thread_tree = ThreadTree()
        self.ctrl_layout.addWidget(self.thread_tree, 0, 0)
        
        self.level_slider = QtGui.QSlider(QtCore.Qt.Horizontal)
        self.level_slider.setMaximum(50)
        self.level_slider.setTickInterval(10)
        self.level_slider.setTickPosition(self.level_slider.TicksAbove)
        self.level_slider.setValue(35)
        self.ctrl_layout.addWidget(self.level_slider, 1, 0)
        self.level_slider.valueChanged.connect(self.level_slider_changed)
        
        self.col_per_thread_check = QtGui.QCheckBox("col per thread")
        self.ctrl_layout.addWidget(self.col_per_thread_check, 2, 0)
        self.col_per_thread_check.toggled.connect(self.col_per_thread_toggled)
        
        self.multiline_check = QtGui.QCheckBox("multiline")
        self.ctrl_layout.addWidget(self.multiline_check, 3, 0)
        self.multiline_check.toggled.connect(self.multiline_toggled)
        
        self.resize(1200, 800)
        
        self.col_per_thread_toggled(False)
        self.level_slider_changed()
        
    def new_record(self, rec):
        self.last_rec = rec
        self.log_records.append(rec)
        item = LogRecordItem(self, rec)
        
        # insert item into time-sorted position
        i = self.tree.topLevelItemCount() - 1
        if i < 0 or rec.created >= self.tree.topLevelItem(i).rec.created:
            self.tree.addTopLevelItem(item)
        else:
            while i > 0 and rec.created < self.tree.topLevelItem(i-1).rec.created:
                i -= 1
            self.tree.insertTopLevelItem(i, item)
        
        item.set_col_per_thread(self.col_per_thread_check.isChecked())
        item.setHidden(rec.levelno < 50-self.level_slider.value())
        
        self.thread_tree.add_thread(item.thread)
        
    def col_per_thread_toggled(self, cpt):
        n_threads = len(ThreadDescriptor.all_threads)
        if cpt:
            self.tree.setColumnCount(n_threads + 1)
            self.tree.setHeaderHidden(False)
            width = max(100, self.tree.width() // self.tree.columnCount())
            for i in range(self.tree.columnCount()):
                self.tree.setColumnWidth(i, width)
            self.tree.setHeaderLabels(['time'] + [t.name for t in ThreadDescriptor.all_threads.values()])
        else:
            self.tree.setColumnCount(3)
            self.tree.setColumnWidth(0, 200)
            self.tree.setColumnWidth(1, 250)
            self.tree.setHeaderHidden(True)
            
        for i in range(self.tree.topLevelItemCount()):
            item = self.tree.topLevelItem(i)
            item.set_col_per_thread(cpt)

    def level_slider_changed(self):
        v = 50 - self.level_slider.value()
        for i in range(self.tree.topLevelItemCount()):
            item = self.tree.topLevelItem(i)
            item.setHidden(item.rec.levelno < v)

    def multiline_toggled(self, ml):
        pass


class LogRecordItem(QtGui.QTreeWidgetItem):
    def __init__(self, logview, rec):
        self.rec = rec
        self._logview = weakref.ref(logview)
        self.thread = ThreadDescriptor.from_log_record(rec)
        self._msg = rec.getMessage()
        tfrac = '%f'%(rec.created - int(rec.created))
        tfrac = tfrac[tfrac.index('.'):]
        self._date_str = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(rec.created)) + tfrac
        QtGui.QTreeWidgetItem.__init__(self)

    def set_col_per_thread(self, cpt):
        blk = pg.mkBrush('k')
        n_threads = len(ThreadDescriptor.all_threads)
        if cpt is False:
            text = [self._date_str, self.thread.name, self._msg]
            self.setForeground(0, blk)
            self.setForeground(1, pg.mkBrush(self.thread.color))
            self.setForeground(2, blk)
        else:
            col = self.thread.index
            text = [self._date_str] + ([''] * n_threads)
            text[col+1] = self._msg
            for i in range(self._logview().tree.columnCount()):
                self.setForeground(i, blk)
            self.setForeground(col+1, pg.mkBrush(self.thread.color))
            
        for i in range(self._logview().tree.columnCount()):
            self.setTextAlignment(i, QtCore.Qt.AlignLeft | QtCore.Qt.AlignTop)
            self.setText(i, text[i])


class ThreadDescriptor(object):
    
    all_threads = OrderedDict()
    _thread_color_list = [
        "#AA0000",
        "#00AA00",
        "#0000AA",
        "#888800",
        "#880088",
        "#008888",
    ]

    @classmethod
    def get(cls, key):
        if key not in cls.all_threads:
            cls.all_threads[key] = cls(key)
        return cls.all_threads[key]

    @classmethod
    def from_log_record(cls, rec):
        hid = getattr(rec, 'hostname', get_host_name())
        pid = getattr(rec, 'process_name', get_process_name())
        tid = getattr(rec, 'thread_name', get_thread_name(rec.thread))
        return cls.get((hid, pid, tid))
    
    def __init__(self, key):
        self.key = key
        self.server_addr = None
        if key in ThreadDescriptor.all_threads:
            raise ValueError("Already created thread descriptor for %s; use "
                "get() instead." % key)
        self.index = len(ThreadDescriptor.all_threads)
        ThreadDescriptor.all_threads[key] = self
        self.name = "%s : %s : %s" % key
        self.color = self._thread_color_list[self.index % len(self._thread_color_list)]
        

class ThreadTree(QtGui.QTreeWidget):
    def __init__(self):
        QtGui.QTreeWidget.__init__(self)
        self.setHeaderHidden(True)

        self.hosts = {}
        self.procs = {}
        self.threads = {}
        
    def add_thread(self, thread):
        key = thread.key
        if key in self.threads:
            return
        
        host_item = self.hosts.get(key[0], None)
        if host_item is None:
            host_item = QtGui.QTreeWidgetItem([key[0]])
            self.addTopLevelItem(host_item)
            self.hosts[key[0]] = host_item
            self.expandItem(host_item)
        
        proc_item = self.procs.get(key[:2], None)
        if proc_item is None:
            proc_item = QtGui.QTreeWidgetItem([key[1]])
            host_item.addChild(proc_item)
            self.procs[key[:2]] = proc_item
            self.expandItem(proc_item)
            
        thread_item = QtGui.QTreeWidgetItem([key[2]])
        thread_item.thread = thread
        self.threads[thread.key] = thread_item
        proc_item.addChild(thread_item)


class QtLogHandler(logging.Handler, QtCore.QObject):
    """Log handler that emits a Qt signal for each record.
    """
    new_record = QtCore.Signal(object)
    
    def __init__(self):
        logging.Handler.__init__(self)
        QtCore.QObject.__init__(self)
        
    def handle(self, record):
        self.new_record.emit(record)
