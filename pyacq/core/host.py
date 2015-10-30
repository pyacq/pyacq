from .rpc import ProcessSpawner
from .nodegroup import NodeGroup

from logging import info


class HostSpawner(ProcessSpawner):
    def __init__(self, name):
        """Spawns a new process with a Host.
        
        This object can be used to control both the spawned process and the
        Host.
        """
        ProcessSpawner.__init__(self)
        self.host = self.client._import('pyacq.core.host').Host(name)

    def create_nodegroup(self, **kwds):
        return self.host.create_nodegroup(**kwds)
    
    def close_all_nodegroups(self, force=False, **kwds):
        return self.host.close_all_nodegruops(force=force, **kwds)

    def set_logger(self, logger, **kwds):
        return self.host.set_logger(logger, **kwds)
    

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
        self.logger = None
        self.spawners = set()

    def create_nodegroup(self, qt=False, addr='tcp://*:*'):
        """Create a new NodeGroup in a new process and return a proxy to it.
        """
        ps = ProcessSpawner(qt=qt)
        rng = ps.client._import('pyacq.core.nodegroup')
        self._set_spawner_logger(ps)
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
        
    def set_logger(self, logger):
        """Set the logger for this host.
        
        All processes spawned from this host will forward their error messages
        to the logger.
        """
        self.logger = logger
        for sp in self.spawners:
            self._set_spawner_logger(sp)
            
    def _set_spawner_logger(self, sp):
        if self.logger is None:
            return
        rlog = sp.client._import('pyacq.core.log')
        rlog.logger = self.logger
