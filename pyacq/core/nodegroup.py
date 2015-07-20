from pyqtgraph.Qt import QtCore, QtGui

from .rpc import RPCServer
from .node import Node, WidgetNode
from .nodelist import all_nodes



class RpcThread( QtCore.QThread):
    def __init__(self, rpc_server, parent = None):
        QtCore.QThread.__init__(self, parent)
        self.rpc_server = rpc_server
    
    def run(self):
        while self.rpc_server.running():
            self.rpc_server._process_one()

class MyApplication(QtGui.QApplication):
    def create_widget_of_node(self):
        node = self.sender()
        node._create_widget()
        
    def show_widget_of_node(self):
        node = self.sender()
        node.widget.show()


class NodeGroup:
    """
    Node gourp is not directly a RPCServer.
    """
    def __init__(self, name, addr):
        self.rpc_server = _NodeGroup(name, addr)
        self.nodes = {}

    def run_forever(self):
        self.app = MyApplication([])
        self.rpc_thread = RpcThread(self.rpc_server, parent = None)
        self.rpc_thread.finished.connect(self.app.quit)
        self.rpc_thread.start()
        self.app.exec_()
    


class _NodeGroup(RPCServer):
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
    
    def create_node(self, name, classname, **kargs):
        #print(self._name, 'create_node', name, classname)
        assert name not in self.nodes, 'This node already exists'
        assert classname in all_nodes, 'The node {} is not registered'.format(classname)
        #print(all_nodes[classname])
        class_ = all_nodes[classname] 
        node = class_(name = name, **kargs)
        
        if isinstance(node, WidgetNode):
            app = QtGui.QApplication.instance()
            node.need_create_widget.connect(app.create_widget_of_node)
            node.need_show_widget.connect(app.show_widget_of_node)
        
        self.nodes[name] = node
    
    def any_node_running(self):
        return any(node.running for node in self.nodes.values())
    
    def delete_node(self, name):
        node = self.nodes[name]
        assert not node.isrunning(), 'The node {} is running'.format(name)
        self.nodes.pop(name)
    
    def control_node(self, name, method, **kargs):
        #print(self._name, 'control_node', name, method)
        getattr(self.nodes[name], method)(**kargs)
    
    
    def start_all(self):
        for node in self.nodes.values():
            node.start()
        
    def stop_all(self):
        for node in self.nodes.values():
            node.stop()


