import atexit
import logging

from .rpc import RPCServer, RPCClient, ProcessSpawner
from .host import Host
from .rpc import log as rpc_log


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
    rpc_log.set_process_name('main_process')
    
    # make nice local log output
    root_logger = logging.getLogger()
    log_handler = rpc_log.RPCLogHandler()
    # for some reason the root logger already has a handler..
    while len(root_logger.handlers) > 0:
        root_logger.removeHandler(root_logger.handlers[0])
    root_logger.addHandler(log_handler)
    
    # Send local uncaught exceptions through logger for nice formatting
    rpc_log.log_exceptions()
        
    # start a global log server
    if rpc_log.get_logger_address() is None:
        rpc_log.start_log_server(logger)
    
    # start the manager
    if mode == 'local':
        if RPCServer.get_server() is None:
            server = RPCServer()
            server.run_lazy()
        man = Manager()
    else:
        logger.info('Spawning remote manager process..')
        proc = ProcessSpawner(name='manager_proc', log_addr=rpc_log.get_logger_address())
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
        
        # Host used for starting nodegroups on the local machine
        self.default_host = Host('default_host')
        
        # for auto-generated node / nodegroup names
        self._next_nodegroup_name = 0
        self._next_node_name = 0
        
        # publish with the RPC server if there is one
        server = RPCServer.get_server()
        if server is not None:
            server['manager'] = self
            
        # If the manager shuts down, then all spawned nodegroups should be
        # closed as well.
        atexit.register(self.close)

    def get_logger_info(self):
        """Return the address of the log server and the level of the root logger.
        """
        return rpc_log.get_logger_address(), logging.getLogger().level
    
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
    
    def disconnect_host(self, host):
        host.close_nodegroups(self)
        self.hosts.pop(host._rpc_addr)

    def list_hosts(self):
        """Return a list of the Hosts that the Manager is connected to.
        """
        return list(self.hosts.values())
    
    def create_nodegroup(self, name=None, host=None, qt=True, **kwds):
        """Create a new NodeGroup process and return a proxy to the NodeGroup.
        
        A NodeGroup is a process that manages one or more Nodes for device
        interaction, computation, or GUI.
        
        Parameters
        ----------
        name : str
            A name for the new NodeGroup's process. This name is used to uniquely
            identify log messages originating from this nodegroup.
        host : None | str | ObjectProxy<Host>
            Optional address of the Host that should be used to spawn the new
            NodeGroup, or a proxy to the Host itself. If omitted, then the
            NodeGroup is spawned from the Manager's default host.
        qt : bool
            Whether to start a QApplication in the new process. Default is True.
            
        All extra keyword arguments are passed to `Host.create_nodegroup()`.
        """
        if name is None:
            name = "nodegroup_%d" % self._next_nodegroup_name
            self._next_nodegroup_name += 1
        assert isinstance(name, str)
        if name in self.nodegroups:
            raise KeyError("Nodegroup named %s already exists" % name)
        if isinstance(host, str):
            host = self.hosts[host]
        if host is None:
            host = self.default_host
            
        # Ask nodegroup to send log records to our server
        if 'log_addr' not in kwds:
            kwds['log_addr'] = rpc_log.get_logger_address()
        if 'log_level' not in kwds:
            kwds['log_level'] = logger.getEffectiveLevel()
        
        ng = host.create_nodegroup(name=name, manager=self, qt=qt, **kwds)
        self.nodegroups[name] = ng
        return ng
    
    def list_nodegroups(self):
        return list(self.nodegroups.values())

    def start_all_nodes(self):
        for ng in self.nodegroups.values():
            ng.start_all_nodes()
    
    def stop_all_nodes(self):
        for ng in self.nodegroups.values():
            ng.stop_all_nodes()

    def close_all_nodegroups(self):
        for ng in self.nodegroups.values():
            try:
                ng.close()
            except RuntimeError:
                # If the server has already disconnected, then no need to close.
                cli = RPCClient.get_client(ng._rpc_addr)
                if not cli.disconnected():
                    raise
        self.nodegroups = {}

    def close(self):
        """Close the Manager.
        
        If a default host was created by this Manager, then it will be closed 
        as well.
        """
        self.close_all_nodegroups()
