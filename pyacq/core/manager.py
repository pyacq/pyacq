from .rpc import RPCServer, RPCClientSocket, RPCClient


class Manager(RPCServer):
    """
    This class:
       * centralize all rpc commands to distribute them
       * centralize all info about all Node, NodeGroup, Host, ...
    """
    def __init__(self, name, addr):
        RPCServer.__init__(self, name, addr)
        self.hosts = {}  # name:HostProxy
        self.nodegroups = {}  # name:NodegroupProxy
        self.nodes = {}  # name:NodeProxy
        
        # shared socket for all RPC client connections
        self._rpc_socket = RPCClientSocket()

    def connect_host(self, name, addr):
        if name not in self.hosts:
            hp = _Host(self, name, addr)
            self.hosts[name] = hp

    def disconnect_host(self, name):
        self.hosts[name].close()

    def list_hosts(self):
        return list(self.hosts.keys())
    
    def add_nodegroup(self, host, name):
        if name in self.nodegroups:
            raise KeyError("Nodegroup named %s already exists" % name)
        host = self.hosts[host]
        addr = 'tcp://%s:*' % (host.rpc_hostname)
        _, addr = host.client.new_nodegroup(name, addr)
        ng = _NodeGroup(self, name, addr)
        host.add_nodegroup(ng)
        self.nodegroups[name] = ng

    def list_nodegroups(self, host=None):
        if host is None:
            return list(self.nodegroups.keys())
        else:
            return self.hosts[host].list_nodegroups()

    def list_nodes(self, nodegroup=None):
        if nodegroup is None:
            return list(self.nodes.keys())
        else:
            return self.nodegroups[nodegroup].list_nodes()

        
class _Host(object):
    def __init__(self, mgr, name, addr):
        self.mgr = mgr
        self.rpc_address = addr
        self.rpc_name = name
        self.client = RPCClient(name, addr)
        self.nodegroups = {}
        self.rpc_hostname = addr.partition('//')[2].rpartition(':')[0]

    def add_nodegroup(self, ng):
        self.nodegroups[ng.rpc_name] = ng
    
    def list_nodegroups(self):
        return list(self.nodegroups.keys())


class _NodeGroup(object):
    def __init__(self, mgr, name, addr):
        self.mgr = mgr
        self.rpc_address = addr
        self.rpc_name = name
        self.client = RPCClient(name, addr)
        self.nodes = {}

    def list_nodes(self):
        return list(self.nodes.keys())
    
        
        