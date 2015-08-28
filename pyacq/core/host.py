from .processspawner import ProcessSpawner
from .rpc import RPCServer, RPCClient
from .nodegroup import NodeGroup

from logging import info

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

    def close(self):
        """
        Close the Host
        And close all its NodeGroup.
        """
        self.close_all_nodegroups()
        RPCServer.close(self)

    
    def create_nodegroup(self, name, addr):
        """Create a new NodeGroup in a new process.
        
        Return the RPC name and address of the new nodegroup.
        """
        assert name not in self.nodegroup_process, 'This node group already exists'
        #print(self._name, 'start_nodegroup', name)
        ps = ProcessSpawner(NodeGroup, name, addr)
        self.nodegroup_process[name] = ps
        return ps.name, ps.addr
    
    def close_nodegroup(self, name, force = False):
        """
        Close a NodeGroup and stop its process.
        """
        client = self.nodegroup_process[name].client
        if not force:
            assert not client.any_node_running(), u'Try to close Host but Node are running'
        self.nodegroup_process[name].stop()
        del self.nodegroup_process[name]

    def close_all_nodegroups(self):
        """Close all NodeGroups belonging to this host.
        """
        for name in list(self.nodegroup_process.keys()):
            self.close_nodegroup(name, force = True)
        
    