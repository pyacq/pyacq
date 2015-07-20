from .rpc import RPCServer, RPCClientSocket, RPCClient


class Manager(RPCServer):
    """
    This class:
       * centralize all rpc commands to distribute them
       * centralize all info about all Node, NodeGroup, Host, ...
    """
    def __init__(self, name, addr):
        RPCServer.__init__(self, name, addr)
        self._hosts = {}
        self._rpc_socket = RPCClientSocket()

    def connect_host(self, name, addr):
        if name not in self._hosts:
            hp = HostProxy(self, name, addr)
            self._hosts[name] = hp
        return self._hosts[name]

    def disconnect_host(self, name):
        pass

    def add_nodegroup(self, host, name):
        addr = ...
        self._hosts[host].client.new_nodegroup(name, addr)
        ng = NodeGroupProxy(self, name, addr)
        self._nodegroups[name] = ng

    def select_free_address(self, host, prot='tcp'):
        pass

        
class HostProxy(object):
    def __init__(self, mgr, name, addr):
        self.mgr = mgr
        self.rpc_address = addr
        self.rpc_name = name
        self.client = RPCClient(name, addr)

    def add_nodegroup(self, name):
        return self.mgr.add_nodegroup(self.rpc_name, name)


class NodeGroupProxy(object):
    def __init__(self, mgr, name, addr):
        self.mgr = mgr
        self.rpc_address = addr
        self.rpc_name = name
        self.client = RPCClient(name, addr)

    
        
        