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
            hp = HostProxy(self, name, addr)
            self.hosts[name] = hp
        return self.hosts[name]

    def disconnect_host(self, name):
        self.hosts[name].close()

    def add_nodegroup(self, host, name):
        host = self.hosts[host]
        addr = 'tcp://%s:*' % (host.rpc_hostname)
        host.client.new_nodegroup(name, addr)
        ng = NodeGroupProxy(self, name, addr)
        self.nodegroups[name] = ng

        
class HostProxy(object):
    def __init__(self, mgr, name, addr):
        self.mgr = mgr
        self.rpc_address = addr
        self.rpc_name = name
        self.client = RPCClient(name, addr)
        self.nodegroups = {}
        self.rpc_hostname = name.partition('//')[2].rpartition(':')[0]

    def add_nodegroup(self, name):
        ng = self.mgr.add_nodegroup(self.rpc_name, name)
        self.nodegroups[name] = ng
        return ng


class NodeGroupProxy(object):
    def __init__(self, mgr, name, addr):
        self.mgr = mgr
        self.rpc_address = addr
        self.rpc_name = name
        self.client = RPCClient(name, addr)

    
        
        