import atexit
import logging

from .rpc import RPCServer, RPCClient, ProcessSpawner
from .host import Host
from .rpc.log import start_log_server, get_logger_address, ColorizingStreamHandler


logger = logging.getLogger(__name__)


def create_manager(mode='rpc', auto_close_at_exit=True):
    """Create a new Manager either in this process or in a new process.
    
    Parameters
    ----------
    mode : str
        Must be 'local' to create the Manager in the current process, or 'rpc'
        to create the Manager in a new process (in which case a proxy to the 
        remote manager will be returned).
    auto_close_at_exit : bool
        If True, then call `Manager.close()` automatically when the calling
        process exits (only used when ``mode=='rpc'``).
    """
    assert mode in ('local', 'rpc'), "mode must be either 'local' or 'rpc'"
    if mode == 'local':
        return Manager()
    else:
        logger.info('Spawning remote manager process..')
        proc = ProcessSpawner(name='manager_proc')
        man = proc.client._import('pyacq.core.manager').Manager()
        if auto_close_at_exit:
            atexit.register(man.close)
        return man
        

class Manager(object):
    """Manager is a central point of control for connecting to hosts, creating
    Nodegroups and Nodes, and interacting with Nodes.
    
    It can either be instantiated directly or in a subprocess and accessed
    remotely by RPC using `create_manager()`.
    
       
    Parameters
    ----------
    name : str
        A unique identifier for this manager.
    addr : str
        The address for the manager's RPC server.
    """
    def __init__(self):
        logger.info('Creating new Manager..')
        self.hosts = {}  # addr:Host
        self.nodegroups = {}  # name:Nodegroup
        self.nodes = {}  # name:Node
        
        # Host used for starting nodegroups on the local machine
        self.default_host = Host('default_host')
        
        # for auto-generated node / nodegroup names
        self._next_nodegroup_name = 0
        self._next_node_name = 0
        
        # make nice local log output
        root_logger = logging.getLogger()
        self.log_handler = ColorizingStreamHandler()
        # for some reason the root logger already has a handler..
        while len(root_logger.handlers) > 0:
            root_logger.removeHandler(root_logger.handlers[0])
        root_logger.addHandler(self.log_handler)
            
        # start a global log server
        start_log_server(logger)
        
        # publish with the RPC server if there is one
        server = RPCServer.get_server()
        if server is not None:
            server['manager'] = self

    def get_logger_info(self):
        """Return the address of the log server and the level of the root logger.
        """
        return get_logger_address(), logging.getLogger().level
    
    def get_host(self, addr):
        """Connect the manager to a Host's RPC server and return a proxy to the
        host.
        
        Hosts are used as a stable service on remote machines from which new
        Nodegroups can be spawned or closed.
        """
        if addr not in self.hosts:
            try:
                cli = RPCClient.get_client(addr)
            except TimeoutError:
                raise TimeoutError("No response from host at %s" % addr)
                
            try:
                self.hosts[addr] = cli['host']
            except KeyError:
                raise ValueError("Contacted %s, but found no Host there." % addr)
        return self.hosts[addr]

    def close(self):
        """Close the Manager.
        
        If a default host was created by this Manager, then it will be closed 
        as well.
        """
        if self.default_host is not None:
            self.default_host.close_all_nodegroups()
            
        # TODO: shut down all known nodegroups?

    def list_hosts(self):
        """Return a list of the addresses for Hosts that the Manager is
        connected to.
        """
        return list(self.hosts.keys())
    
    def create_nodegroup(self, name, host=None, **kwds):
        """Create a new NodeGroup process and return a proxy to the NodeGroup.
        
        A NodeGroup is a process that manages one or more Nodes for device
        interaction, computation, or GUI.
        
        Parameters
        ----------
        name : str
            A unique identifier for the new NodeGroup.
        host : None | str | ObjectProxy<Host>
            Optional address of the Host that should be used to spawn the new
            NodeGroup, or a proxy to the Host itself. If omitted, then the
            NodeGroup is spawned from the Manager's default host.
            
        All extra keyword arguments are passed to `Host.create_nodegroup()`.
        """
        assert isinstance(name, str)
        if name in self.nodegroups:
            raise KeyError("Nodegroup named %s already exists" % name)
        if isinstance(host, str):
            host = self.hosts[host]
        if host is None:
            host = self.default_host
            
        # Ask nodegroup to send log records to our server
        if 'log_addr' not in kwds:
            kwds['log_addr'] = get_logger_address()
        if 'log_level' not in kwds:
            kwds['log_level'] = logger.getEffectiveLevel()
        
        ng = host.create_nodegroup(name, self, **kwds)
        self.nodegroups[name] = ng
        return ng
    
    def list_nodegroups(self):
        return list(self.nodegroups.keys())

    def create_node(self, nodegroup, name, classname, **kwargs):
        if name in self.nodes:
            raise KeyError("Node named %s already exists" % name)
        ng = self.nodegroups[nodegroup]
        ng.client.create_node(name, classname, **kwargs)
        node = Manager._Node(ng, name, classname)
        self.nodes[name] = node
        ng.add_node(name, node)

    def list_nodes(self, nodegroup=None):
        if nodegroup is None:
            return list(self.nodes.keys())
        else:
            return self.nodegroups[nodegroup].list_nodes()

    def control_node(self, name, method, **kwargs):
        ng = self.nodes[name].nodegroup
        return ng.client.control_node(name, method, **kwargs)
    
    def delete_node(self, name):
        ng = self.nodes[name].nodegroup
        ng.client.delete_node(name)
        del self.nodes[name]
        ng.delete_node(name)

    def suggest_nodegroup_name(self):
        name = 'nodegroup-%d' % self._next_nodegroup_name
        self._next_nodegroup_name += 1
        return name
    
    def suggest_node_name(self):
        name = 'node-%d' % self._next_node_name
        self._next_node_name += 1
        return name
    
    def start_all_nodes(self):
        for ng in self.nodegroups.values():
            ng.client.start_all_nodes()
    
    def stop_all_nodes(self):
        for ng in self.nodegroups.values():
            ng.client.stop_all_nodes()

