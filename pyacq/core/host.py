from .rpc import ProcessSpawner, RPCServer
from .nodegroup import NodeGroup


class Host(object):
    """
    Host serves as a pre-existing contact point for spawning
    new processes on a remote machine. 
    
    One Host instance must be running on each machine that will be connected
    to by a Manager. The Host is only responsible for creating and destroying
    NodeGroups.
    """
    @staticmethod
    def spawn(name, **kwds):
        proc = ProcessSpawner(name=name, **kwds)
        host = proc.client._import('pyacq.core.host').Host(name)
        return proc, host
    
    def __init__(self, name):
        self.name = name
        self.spawners = set()
        
        # Publish this object so we can easily retrieve it from any other
        # machine.
        server = RPCServer.get_server()
        if server is not None:
            server['host'] = self

    def create_nodegroup(self, name, manager=None, qt=True, **kwds):
        """Create a new NodeGroup in a new process and return a proxy to it.
        
        Parameters:
        -----------
        name : str
            The name of the new NodeGroup. This will also be used as the name
            of the process in log records sent to the Manager.
        manager : Manager | ObjectProxy<Manager> | None
            The Manager to which this NodeGroup belongs.
        qt : bool
            Whether to start a QApplication in the new process. Default is True.
            
        All extra keyword arguments are passed to `ProcessSpawner()`.
        """
        ps = ProcessSpawner(name=name, qt=qt, **kwds)
        rng = ps.client._import('pyacq.core.nodegroup')
        
        # create nodegroup in remote process
        ps._nodegroup = rng.NodeGroup(host=self, manager=manager)
        
        # publish so others can easily connect to the nodegroup
        ps.client['nodegroup'] = ps._nodegroup
        
        ps._manager = manager
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
        self.spawners = set()
