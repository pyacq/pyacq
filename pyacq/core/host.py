from .processspawner import ProcessSpawner
from .rpc import RPCServer, RPCClient
from .nodegroup import NodeGroup


class Host(RPCServer):
    """
    This class:
       * must run_forever or spawn on each host
       * has the responsability to spawn (by rpc command) some NodeGroup
       
    Parameters
    ----------
    name : str
        The identifier of the host server.
    addr : URL
        Address of RPC server to connect to.
    """
    def __init__(self, name, addr):
        RPCServer.__init__(self, name, addr)
        self.nodegroup_process = {}
    
    def new_nodegroup(self, name, addr):
        """Create a new NodeGroup in a new process.
        
        Return the RPC name and address of the new nodegroup.
        """
        assert name not in self.nodegroup_process, 'This node group already exists'
        #print(self._name, 'start_nodegroup', name)
        ps = ProcessSpawner(NodeGroup, name, addr)
        self.nodegroup_process[name] = ps
        return ps.name, ps.addr
    
    def close_nodegroup(self, name):
        """
        Close a NodeGroup and stop its process.
        """
        #print(self._name, 'stop_nodegroup')
        
        # TODO Ensure that all Node in NodeGroup are not running.
        
        client = RPCClient(name, self.nodegroup_process[name].addr)
        assert not client.any_node_running()
        self.nodegroup_process[name].stop()
        del self.nodegroup_process[name]

    def close_all_nodegroups(self):
        """Close all NodeGroups belonging to this host.
        """
        for name, spawner in self.nodegroup_process:
            spawner.kill()
        self.nodegroup_process = {}
        
    