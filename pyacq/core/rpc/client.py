import time
from logging import info

from .client_socket import RPCClientSocket


class RPCClient(object):
    """Connection to an RPC server.
    
    This class is a proxy for methods provided by the remote server. It is
    meant to be used by accessing and calling remote procedure names::
    
        client = RPCClient('tcp://localhost:5274')
        future = client.my_remote_procedure_name(...)
        result = future.result()
        
    Parameters
    ----------
    name : str
        The identifier used by the remote server.
    addr : URL
        Address of RPC server to connect to.
    rpc_socket : None or RPCClientSocket
        Optional RPCClientSocket with which to connect to the server. This
        allows multiple RPC connections to share a single socket.
    """
    def __init__(self, name, addr, rpc_socket=None):
        if rpc_socket is None:
            rpc_socket = RPCClientSocket()
        info("RPC connect %s => %s@%s", rpc_socket._name, name, addr)
        rpc_socket.connect(addr)
        self._name = name.encode()
        self._rpc_socket = rpc_socket
        self._methods = {}
        self._connect_established = False
        self._establishing_connect = False
        
    def __getattr__(self, name):
        return self._methods.setdefault(name, RPCMethod(self, name))
    
    def _call_method(self, method_name, *args, **kwds):
        """Request the remote server to call a method.
        """
        sync = kwds.pop('_sync', True)
        timeout = kwds.pop('_timeout', None)
        
        if not self._connect_established:
            self._ensure_connection()
        
        fut = self._rpc_socket.send(self._name, 'call', method_name, *args, **kwds)
        
        if sync:
            return fut.result(timeout=timeout)
        else:
            return fut

    def _ensure_connection(self, timeout=3):
        """Make sure RPC server is connected and available.
        """
        if self._establishing_connect:
            return
        self._establishing_connect = True
        try:
            start = time.time()
            while time.time() < start + timeout:
                fut = self.ping(_sync=False)
                try:
                    result = fut.result(timeout=0.1)
                    self._connect_established = True
                    return
                except TimeoutError:
                    continue
            raise TimeoutError("Could not establish connection with RPC server.")
        finally:
            self._establishing_connect = False

    
class RPCMethod(object):
    """A proxy to a single remote procedure.
    
    Calling this object invokes the remote procedure and returns a Future
    instance.
    """
    def __init__(self, client, method):
        self.client = client
        self.method = method
        
    def __call__(self, *args, **kwds):
        return self.client._call_method(self.method, *args, **kwds)
