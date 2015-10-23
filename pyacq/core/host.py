from .nodegroup import NodeGroup

from logging import info


class Host(object):
    """
    Host serves as a pre-existing contact point for spawning
    new processes on a remote machine. 
    
    One Host instance must be running on each machine that will be connected
    to by a Manager. The Host is only responsible for creating and destroying
    NodeGroups.
    """
    def __init__(self, name):
        self.name = name
        self.spawners = set()

    def create_nodegroup(self, qt=False, addr='tcp://*:*'):
        """Create a new NodeGroup in a new process and return a proxy to it.
        """
        ps = ProcessSpawner(qt=qt)
        rng = ps.client._import('pyacq.core.nodegroup')
        ps._nodegroup = rng.NodeGroup()
        self.spawners.add(ps)
        return ps._nodegroup

    def close_all_nodegroups(self, force=False):
        """Close all NodeGroups belonging to this host.
        """
        for sp in self.spawners:
            if force:
                sp.kill()
            else:
                sp.stop()
        
    
