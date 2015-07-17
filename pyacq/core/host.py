
from .processspawner import ProcessSpawner
from .rpc import RPCServer
from .nodegroup import NodeGroup


class Host(RPCServer):
    """
    This class:
       * must run_forever or spwn on each host
       * has the responsability to spawn (by rpc command) some NodeGroup
    """
    def __init__(self, name, addr):
        RPCServer.__init__(self, name, addr)
        self.nodegroup_process = {}
    
    def start_nodegroup(self, name, addr):
        assert name not in self.nodegroup_process, 'This node group already exists'
        self.nodegroup_process[name] = ProcessSpawner(NodeGroup, name, addr)
    
    def stop_nodegroup(self, name):
        self.nodegroup_process[name].stop()
