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
import logging


class RpcThreadSocket( QtCore.QThread):
    # Thread to poll RPC socket and relay requests as `new_message` signal.
    # Return values are delivered back to the thread via self.local_socket.
    new_message = QtCore.Signal(QtCore.QByteArray, QtCore.QByteArray)
    def __init__(self, rpc_server, local_addr, parent = None):
        QtCore.QThread.__init__(self, parent)
        self.rpc_socket = weakref.ref(rpc_server._socket)
        
        context = zmq.Context.instance()
        self.local_socket = context.socket(zmq.PAIR)
        self.local_socket.connect(local_addr)
        
        self.poller = zmq.Poller()
        self.poller.register(self.rpc_socket(), zmq.POLLIN)
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
                        self.local_socket.close()
                        break
            
            socks = dict(self.poller.poll(timeout = 100))
            
            if self.rpc_socket() in socks:
                name, msg = self.rpc_socket().recv_multipart()
                self.new_message.emit(name, msg)
            
            if self.local_socket in socks:
                name, data = self.local_socket.recv_multipart()
                self.rpc_socket().send_multipart([name, data])

    def stop(self):
        with self.lock:
            self.running = False


class NodeGroup(RPCServer):
    """
    NodeGroup is responsible for managing a collection of Nodes within a single
    process.
    
    NodeGroups run an RPC server that allows the Manager to remotely create, 
    manage, and destroy Node instances. All remote interaction with Nodes is done
    via the NodeGroup RPC interface.
    
    Internally, a NodeGroup creates a QApplication for any GUI Nodes to use, and
    all RPC requests are processed in the main thread of the GUI event loop.
    
    NodeGroups themselves are created and destroyed by Hosts, which manage all 
    NodeGroups on a particular machine.
    """
    def __init__(self, name, addr):
        RPCServer.__init__(self, name, addr)
        self.app = QtGui.QApplication([])
        self.nodes = {}

    def run_forever(self):
        """Begin the Qt event loop and listen for RPC requests until `close()`
        is called.
        """
        # create a proxy socket between RpcThreadSocket and main
        addr = 'inproc://'+''.join(random.SystemRandom().choice(string.ascii_uppercase + string.digits) for _ in range(16))
        context = zmq.Context.instance()
        self._local_socket = context.socket(zmq.PAIR)
        self._local_socket.bind(addr)
        
        self._rpcsocket_thread = RpcThreadSocket(self, addr,  parent = self.app)
        self._rpcsocket_thread.new_message.connect(self._mainthread_process_one)
        self._rpcsocket_thread.start()
        
        self.app.setQuitOnLastWindowClosed(False)
        self.app.exec_()
    
    def _mainthread_process_one(self, name, msg):
        self._process_one(bytes(name), bytes(msg))

        if  not self.running():
            # stop the RPC
            self._rpcsocket_thread.stop()
            self._rpcsocket_thread.wait()

            # stop/close all Nodes
            for node in self.nodes.values():
                if node.running():
                    try:
                        node.stop()
                    except:
                        logging.info("Error Node.stop: %s ", node.name)
            for node in self.nodes.values():
                try:
                    node.close()
                except:
                    logging.info("Error Node.close: %s", node.name)
            
            # Quit QApp
            self.app.quit()
            del self.app
   
    def _send_result(self, name, data):
        # over writte RPCServer._send_result to avoid send back the result in main thread
        self._local_socket.send_multipart([name, data])

    def create_node(self, name, classname, **kargs):
        """Create a new Node.
        
        Parameters
        ----------
        name : str
            The name to assign to the new Node. This name must be unique.
        classname : str
            The name of the class from which to instantiate the new Node.
            The class name must be one that was registered using one of the 
            `register_node_type_` methods.
        kargs : 
            All extra keyword arguments are passed to the Node's constructor.
        """
        assert name not in self.nodes, 'This node already exists'
        assert classname in all_nodes, 'The node {} is not registered'.format(classname)
        class_ = all_nodes[classname] 
        node = class_(name = name, **kargs)
        self.nodes[name] = node
    
    def delete_node(self, name):
        """Delete a Node from this NodeGroup.
        
        Parameters
        ----------
        name : str
            The name of the Node to delete.
        """
        node = self.nodes[name]
        assert not node.running(), 'The node {} is running'.format(name)
        node.close()
        self.nodes.pop(name)
    
    def control_node(self, nodename, method, *args, **kargs):
        """Call a method on a Node.
        
        Parameters
        ----------
        nodename : str
            The name of the Node to interact with.
        method : str
            The name of the method to call.
        
        All other positional and keyword arguments are passed to the method call.
        """
        return getattr(self.nodes[nodename], method)(*args, **kargs)
    
    def set_node_attr(self, nodename, attr, value):
        """Set an attribute on a Node.
        """
        return setattr(self.nodes[nodename], attr, value)
    
    def get_node_attr(self, nodename, attr):
        """Get an attribute from a Node.
        """
        return getattr(self.nodes[nodename], attr)
    
    def register_node_type_from_module(self, module, classname):
        """Import a Node subclass and register it.
        """
        mod = importlib.import_module(module)
        class_= getattr(mod, classname)
        register_node_type(class_,classname = classname)
    
    def register_node_type_with_pickle(self, picklizedclass, classname):
        """Unpickle a Node subclass and register it.
        """
        # this is not working at the moment, so bad....
        class_ = pickle.loads(picklizedclass)
        register_node_type(class_,classname = classname)

    def start_all_nodes(self):
        """Call `Node.start()` for all Nodes in this group.
        """
        for node in self.nodes.values():
            node.start()
        
    def stop_all_nodes(self):
        """Call `Node.stop()` for all Nodes in this group.
        """
        for node in self.nodes.values():
            node.stop()

    def any_node_running(self):
        """Return True if any of the Nodes in this group are running.
        """
        return any(node.running() for node in self.nodes.values())
