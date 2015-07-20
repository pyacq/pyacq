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
            hp = _Host(name, addr)
            self.hosts[name] = hp

    def disconnect_host(self, name):
        self.hosts[name].close()

    def list_hosts(self):
        return list(self.hosts.keys())
    
    def create_nodegroup(self, host, name):
        if name in self.nodegroups:
            raise KeyError("Nodegroup named %s already exists" % name)
        host = self.hosts[host]
        addr = 'tcp://%s:*' % (host.rpc_hostname)
        _, addr = host.client.new_nodegroup(name, addr)
        ng = _NodeGroup(host, name, addr)
        host.add_nodegroup(ng)
        self.nodegroups[name] = ng

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
        node = _Node(ng, name, classname)
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

        
class _Host(object):
    def __init__(self, name, addr):
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
    def __init__(self, host, name, addr):
        self.host = host
        self.rpc_address = addr
        self.rpc_name = name
        self.client = RPCClient(name, addr)
        self.nodes = {}

    def add_node(self, name, node):
        self.nodes[name] = node

    def list_nodes(self):
        return list(self.nodes.keys())

    def delete_node(self, name):
        del self.nodes[name]
    
        
class _Node(object):
    def __init__(self, nodegroup, name, classname):
        self.nodegroup = nodegroup
        self.name = name
        self.classname = classname
        