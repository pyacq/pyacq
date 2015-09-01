from pyqtgraph.Qt import QtCore, QtGui
from pyqtgraph.util.mutex import Mutex

from .rpc import RPCServer
from .node import Node, WidgetNode, register_node_type
from .nodelist import all_nodes

import time
import importlib
import pickle
import weakref
import random
import string
import zmq

class RpcThreadSocket( QtCore.QThread):
    new_message = QtCore.Signal(QtCore.QByteArray, QtCore.QByteArray)
    def __init__(self, rpc_server, local_addr, parent = None):
        QtCore.QThread.__init__(self, parent)
        self.rpc_server = rpc_server
        self.rpc_socket = rpc_server._socket
        
        context = zmq.Context.instance()
        self.local_socket = context.socket(zmq.PAIR)
        self.local_socket.connect(local_addr)
        
        self.poller = zmq.Poller()
        self.poller.register(self.rpc_socket, zmq.POLLIN)
        self.poller.register(self.local_socket, zmq.POLLIN)
    
        self.running = False
        self.lock = Mutex()
    
    def run(self):
        with self.lock:
            self.running = True
        
        while True:
            with self.lock:
                if not self.running:
                    # do a last poll
                    socks = dict(self.poller.poll(timeout = 500))
                    if len(socks)==0:
                        break
            
            socks = dict(self.poller.poll(timeout = 100))
            
            if self.rpc_socket in socks:
                name, msg = self.rpc_server._read_socket()
                self.new_message.emit(name, msg)
            
            if self.local_socket in socks:
                name, data = self.local_socket.recv_multipart()
                self.rpc_socket.send_multipart([name, data])

    def stop(self):
        with self.lock:
            self.running = False


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
        # create a proxy socket between RpcThreadSocket and main
        addr = 'inproc://'+''.join(random.SystemRandom().choice(string.ascii_uppercase + string.digits) for _ in range(16))
        context = zmq.Context.instance()
        self._local_socket = context.socket(zmq.PAIR)
        self._local_socket.bind(addr)
        
        self._rpcsocket_thread = RpcThreadSocket(self, addr,  parent = None)
        self._rpcsocket_thread.new_message.connect(self._mainthread_process_one)
        self._rpcsocket_thread.start()
        
        self.app.exec_()
    
    def _mainthread_process_one(self, name, msg):
        self._process_one(bytes(name), bytes(msg))
        
        if  not self.running():
            self._rpcsocket_thread.stop()
            self._rpcsocket_thread.wait()
            self._socket.close()
            self.app.quit()

    def _send_result(self, name, data):
        # over writte RPCServer._send_result to avoid send back the result in main thread
        self._local_socket.send_multipart([name, data])

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
