from pyqtgraph.Qt import QtCore, QtGui

from .rpc import RPCServer
from .node import Node, WidgetNode
from .nodelist import all_nodes

import time

class ThreadReadSocket( QtCore.QThread):
    new_message = QtCore.Signal(QtCore.QByteArray, QtCore.QByteArray)
    def __init__(self, rpc_server, parent = None):
        QtCore.QThread.__init__(self, parent)
        self.rpc_server = rpc_server
    
    def run(self):
        name, msg = self.rpc_server._read_socket()
        self.new_message.emit(name, msg)
    
class NodeGroupApplication(QtGui.QApplication):
    def create_widget_of_node(self):
        node = self.sender()
        node.create_widget()
        
    #~ def show_widget_of_node(self):
        #~ node = self.sender()
        #~ node.widget.show()



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
        self.nodes = {}

    def run_forever(self):
        self.app = NodeGroupApplication([])
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
        #~ print(self._name, 'create_node', name, classname)
        assert name not in self.nodes, 'This node already exists'
        assert classname in all_nodes, 'The node {} is not registered'.format(classname)
        #print(all_nodes[classname])
        class_ = all_nodes[classname] 
        node = class_(name = name, **kargs)
        #~ print(node.thread())
        #~ print(node.parent())
        node.moveToThread(QtGui.QApplication.instance().thread())
        #~ print(QtGui.QApplication.instance().thread())
        #~ print(node.thread())
        #~ print(node.parent())
        self.nodes[name] = node
    
    def any_node_running(self):
        return any(node.running() for node in self.nodes.values())
    
    def delete_node(self, name):
        node = self.nodes[name]
        assert not node.running(), 'The node {} is running'.format(name)
        self.nodes.pop(name)
    
    def control_node(self, name, method, *args, **kargs):
        #node are living in main thread so need signal to remote then
        #print(self._name, 'control_node', name, method)
        #~ self.rpc_thread.need_control_node.emit(name, method, *args, **kargs)
        getattr(self.nodes[name], method)(*args, **kargs)
        #~ QtGui.QApplication.instance().postEvent(self.rpc_thread)
        
    
    def start_all(self):
        for node in self.nodes.values():
            node.start()
        
    def stop_all(self):
        for node in self.nodes.values():
            node.stop()


