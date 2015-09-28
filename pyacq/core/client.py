from .rpc import RPCClient



class ManagerProxy(RPCClient):
    def __init__(self, name, addr, manager_process = None):
        RPCClient.__init__(self, name, addr)
        self._host_proxy = {}
        
        self.manager_process = manager_process # needed for properlly close and wait the process

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
    
    def close(self):
        self._call_method('close')
        if self.manager_process is not None:
            self.manager_process.proc.wait()


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


# I do not like so much theses 3 class
# they duplicate what do Node and so need to introduce
# maybe we need a better generic Proxy object for both NodeProxy/OutputStreamProxy/InputStreamProxy
# this would be a simlimar system  to ObjectProxy/DeferredObjectProxy in pyqtgraph.multiprocess.remoteproxy
# to get acces to all object (and there attribute/method) inside a RPCClient

# we can keep them for the moment

class NodeProxy(object):
    def __init__(self, nodegroup, name):
        self.nodegroup = nodegroup
        self.name = name
        self.inputs = { name:InputStreamProxy(self, name) for name in self.nodegroup.get_node_attr(self.name, '_input_specs').keys()}
        self.outputs = { name:OutputStreamProxy(self, name) for name in self.nodegroup.get_node_attr(self.name, '_output_specs').keys()}
        
        
    def __getattr__(self, name):
        return lambda *args, **kwargs: getattr(self.nodegroup, 'control_node')(self.name, name, *args, **kwargs)

    @property
    def input(self):
        assert len(self.inputs)==1, 'Node.input is a shortcut when Node have only 1 input ({} here)'.format(len(self.inputs))
        return list(self.inputs.values())[0]
    
    @property
    def output(self):
        assert len(self.outputs)==1, 'Node.output is a shortcut when Node have only 1 output ({} here)'.format(len(self.outputs))
        return list(self.outputs.values())[0]
        

class OutputStreamProxy:
    def __init__(self, node, name):
        self.node = node
        self.name = name
    
    def configure(self, **kargs):
        self.node.configure_output(self.name, **kargs)
    
    @property
    def params(self):
        return self.node.get_output(self.name)
    
class InputStreamProxy:
    def __init__(self, node, name):
        self.node = node
        self.name = name
    
    def connect(self, output):
        if isinstance(output, dict):
            self.node.connect_input(self.name, output)
        else:
            self.node.connect_input(self.name, output.params)
        
        

    @property
    def params(self):
        return self.node.get_output(self.name)

