from .rpc import ProcessSpawner, RPCServer
from . import nodelist


class NodeGroup(object):
    """
    NodeGroup is responsible for managing a collection of Nodes within a single
    process.
    
    NodeGroups themselves are created and destroyed by Hosts, which manage all 
    NodeGroups on a particular machine.
    """
    
    
    def __init__(self, host):
        self.host = host
        self.nodes = set()

    def create_node(self, node_class, *args, **kwds):
        """Create a new Node and add it to this NodeGroup.
        
        Return the new Node.
        """
        assert isinstance(node_class, str)
        cls = nodelist.all_nodes[node_class]
        node = cls(*args, **kwds)
        self.add_node(node)
        return node

    def list_node_types(self):
        """Return a list of the class names for all registered node types.
        """
        return list(nodelist.all_nodes.keys())

    def add_node(self, node):
        """Add a Node to this NodeGroup.
        """
        self.nodes.add(node)
        
    def remove_node(self, node):
        """Remove a Node from this NodeGroup.
        """
        self.nodes.remove(node)
    
    def start_all_nodes(self):
        """Call `Node.start()` for all Nodes in this group.
        """
        for node in self.nodes:
            node.start()
        
    def stop_all_nodes(self):
        """Call `Node.stop()` for all Nodes in this group.
        """
        for node in self.nodes:
            node.stop()

    def any_node_running(self):
        """Return True if any of the Nodes in this group are running.
        """
        return any(node.running() for node in self.nodes)

    def close(self):
        RPCServer.get_server().close()
