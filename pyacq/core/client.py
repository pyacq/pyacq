from .rpc import RPCClient



class ManagerProxy(RPCClient):
    def __init__(self, name, addr):
        RPCClient.__init__(self, name, addr)
        self._host_proxy = {}

    def connect_host(self, name, addr):
        self._call_method('connect_host', name, addr)
        if name not in self._host_proxy:
            self._host_proxy[name] = HostProxy(name, addr)
        return self._host_proxy[name]
    
    def default_host(self):
        name, addr = self._call_method('default_host')
        if name not in self._host_proxy:
            self._host_proxy[name] = HostProxy(self, name, addr)
        return self._host_proxy[name]

    def create_nodegroup(self, name=None):
        """
        """
        host = self.default_host()
        return host.create_nodegroup(name)
    

class HostProxy(RPCClient):
    def __init__(self, mgr, name, addr):
        self.mgr = mgr
        self.name = name
        self.addr = addr
        RPCClient.__init__(self, name, addr)
        self._nodegroup_proxy = {}
        
    def create_nodegroup(self, name=None):
        if name is None:
            name = self.mgr.suggest_nodegroup_name()
        _, addr = self.mgr._call_method('create_nodegroup', self.name, name)
        self._nodegroup_proxy[name] = NodeGroupProxy(self, name, addr)
        return self._nodegroup_proxy[name]


class NodeGroupProxy(RPCClient):
    def __init__(self, host, name, addr):
        self.mgr = host.mgr
        self.host = host
        self.name = name
        self.addr = addr
        RPCClient.__init__(self, name, addr)
        self._node_proxy = {}
        
    def create_node(self, classname, name=None, **kwargs):
        if name is None:
            name = self.mgr.suggest_node_name()
        self.mgr.create_node(self.name, name, classname, **kwargs)
        self._node_proxy[name] = NodeProxy(self, name)
        return self._node_proxy[name]
        
class NodeProxy(object):
    def __init__(self, nodegroup, name):
        self.nodegroup = nodegroup
        self.name = name
        
    def __getattr__(self, name):
        return lambda *args, **kwargs: getattr(self.nodegroup, 'control_node')(self.name, name, *args, **kwargs)
