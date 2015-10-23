import atexit

from .rpc import RPCServer, RPCClient, ProcessSpawner
from .host import Host

import logging


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
        return Manager(name='manager', addr='tcp://*:*')
    else:
        proc = ProcessSpawner(Manager, name='manager', addr='tcp://127.0.0.1:*')
        man = ManagerProxy(proc.name, proc.addr, manager_process=proc)
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
    def __init__(self, name, addr, manager_process=None):
        RPCServer.__init__(self, name, addr)
        
        self.hosts = {}  # name:HostProxy
        self.nodegroups = {}  # name:NodegroupProxy
        self.nodes = {}  # name:NodeProxy
        
        # auto-generated host on the local machine
        self._default_host = None
        
        # for auto-generated node / nodegroup names
        self._next_nodegroup_name = 0
        self._next_node_name = 0
    
    def connect_host(self, name, addr):
        """Connect the manager to a Host.
        
        Hosts are used as a stable service on remote machines from which new
        Nodegroups can be spawned or closed.
        """
        if name not in self.hosts:
            hp = Manager._Host(name, addr)
            self.hosts[name] = hp

    def disconnect_host(self, name):
        """Disconnect the Manager from the Host identified by *name*.
        """
        for ng in self.hosts[name]:
            self.nodegroups.pop(ng.name)
        self.hosts.pop(name)
    
    def default_host(self):
        """Return the RPC name and address of a default Host created by the
        Manager.
        """
        if self._default_host is None:
            addr = self._addr.rpartition(b':')[0] + b':*'
            proc = ProcessSpawner(Host, name='default-host', addr=addr)
            self._default_host = proc
            self.connect_host(proc.name, proc.addr)
        return self._default_host.name, self._default_host.addr
    
    def close_host(self, name):
        """Close the Host identified by *name*.
        """
        self.hosts[name].client.close()
    
    def close(self):
        """Close the Manager.
        
        If a default host was created by this Manager, then it will be closed 
        as well.
        """
        if self._default_host is not None:
            self._default_host.stop()
        RPCServer.close(self)

    def list_hosts(self):
        """Return a list of the identifiers for Hosts that the Manager is
        connected to.
        """
        return list(self.hosts.keys())
    
    def create_nodegroup(self, host, name):
        """Create a new NodeGroup.
        
        A NodeGroup is a process that manages one or more Nodes for device
        interaction, computation, or GUI.
        
        Parameters
        ----------
        host : str
            The identifier of the Host that should be used to spawn the new
            Nodegroup.
        name : str
            A unique identifier for the new Nodegroup.
        """
        if name in self.nodegroups:
            raise KeyError("Nodegroup named %s already exists" % name)
        host = self.hosts[host]
        addr = 'tcp://%s:*' % (host.rpc_hostname)
        _, addr = host.client.create_nodegroup(name, addr)
        ng = Manager._NodeGroup(host, name, addr)
        host.add_nodegroup(ng)
        self.nodegroups[name] = ng
        return name, addr
    
    #~ def close_nodegroup(self, name):
        #~ self.nodegroups[name].host.client.close_nodegroup(name)

    def list_nodegroups(self, host=None):
        if host is None:
            return list(self.nodegroups.keys())
        else:
            return self.hosts[host].list_nodegroups()

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

