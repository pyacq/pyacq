import re
import logging
import atexit

from .rpc import ProcessSpawner, RPCServer
from .nodegroup import NodeGroup

logger = logging.getLogger()


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
    
    def __init__(self, name, poll_procs=False):
        self.name = name
        self.spawners = []
        
        # Publish this object so we can easily retrieve it from any other
        # machine.
        server = RPCServer.get_server()
        if server is not None:
            server['host'] = self
            if poll_procs:
                self.timer = server.start_timer(self.check_spawners, interval=1.0)
                
        atexit.register(self.close_all_nodegroups)

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
        server = RPCServer.get_server()
        addr = re.sub(r':\d+$', ':*', server.address.decode())
        sp = ProcessSpawner(name=name, qt=qt, address=addr, **kwds)
        logger.info("Process started: %s" % sp)
        rng = sp.client._import('pyacq.core.nodegroup')
        
        # create nodegroup in remote process
        sp._nodegroup = rng.NodeGroup(host=self, manager=manager)
        
        # publish so others can easily connect to the nodegroup
        sp.client['nodegroup'] = sp._nodegroup
        
        sp._manager = manager
        self.spawners.append(sp)
        return sp._nodegroup

    def close_all_nodegroups(self, force=False):
        """Close all NodeGroups belonging to this host.
        """
        for sp in self.spawners:
            if force:
                sp.kill()
            else:
                sp.stop()
        self.spawners = []

    def check_spawners(self):
        """Check for any processes that have exited and report them to their
        manager.
        
        This method is called by a timer if the host is created with *poll_procs*
        True.
        """
        for sp in self.spawners[:]:
            rval = sp.poll()
            if sp.poll() is not None:
                logger.info("Process exited: %s" % sp)
                self.spawners.remove(sp)
                sp._manager.nodegroup_closed(sp._nodegroup, _sync='off')
        