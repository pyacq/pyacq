from pyqtgraph.Qt import QtCore, QtGui
from pyqtgraph.util.mutex import Mutex

from .rpc import RPCServer
from .node import Node, WidgetNode, register_node_type
from .nodelist import all_nodes

import time
import importlib
import pickle

class ThreadReadSocket( QtCore.QThread):
    new_message = QtCore.Signal(QtCore.QByteArray, QtCore.QByteArray)
    def __init__(self, rpc_server, parent = None):
        QtCore.QThread.__init__(self, parent)
        self.rpc_server = rpc_server
    
    def run(self):
        name, msg = self.rpc_server._read_socket()
        self.new_message.emit(name, msg)

class NodeGroup(RPCServer):
    """
    This class:
       * is a bunch of Node inside a process.
       * lauched/stoped by Host
       * able to create/delete Node (by rpc command)
       * distribute the start/stop/initialize/configure to appropriate Node
    """
    
    def __init__(self, name, addr):
        RPCServer.__init__(self, name, addr)
        self.app = QtGui.QApplication([])
        self.nodes = {}

    def run_forever(self):
        self._readsocket_thread = ThreadReadSocket(self, parent = None)
        self._readsocket_thread.new_message.connect(self._mainthread_process_one)
        self._readsocket_thread.start()
        self.app.exec_()
    
    def _mainthread_process_one(self, name, msg):
        self._readsocket_thread.wait()
        self._process_one(bytes(name), bytes(msg))
        if self.running():
            self._readsocket_thread.start()
        else:
            self.app.quit()

    def create_node(self, name, classname, **kargs):
        assert name not in self.nodes, 'This node already exists'
        assert classname in all_nodes, 'The node {} is not registered'.format(classname)
        class_ = all_nodes[classname] 
        node = class_(name = name, **kargs)
        self.nodes[name] = node
    
    def delete_node(self, name):
        node = self.nodes[name]
        assert not node.running(), 'The node {} is running'.format(name)
        self.nodes.pop(name)
    
    def control_node(self, nodename, method, *args, **kargs):
        return getattr(self.nodes[nodename], method)(*args, **kargs)
    
    def set_node_attr(self, nodename, attr, value):
        return setattr(self.nodes[nodename], attr, value)
    
    def get_node_attr(self, nodename, attr):
        return getattr(self.nodes[nodename], attr)
    
    def register_node_type_from_module(self, module, classname):
        mod = importlib.import_module(module)
        class_= getattr(mod, classname)
        register_node_type(class_,classname = classname)
    
    def register_node_type_with_pickle(self, picklizedclass, classname):
        # this is not working at the moment, so bad....
        class_ = pickle.loads(picklizedclass)
        register_node_type(class_,classname = classname)

    def start_all_nodes(self):
        for node in self.nodes.values():
            node.start()
        
    def stop_all_nodes(self):
        for node in self.nodes.values():
            node.stop()

    def any_node_running(self):
        return any(node.running() for node in self.nodes.values())
