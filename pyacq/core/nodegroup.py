from .rpc import ProcessSpawner


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

    def add_node(self, node):
        self.nodes.add(node)
        
    def remove_node(self, node):
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
        self.server.close()
