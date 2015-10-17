import sys
import time
import traceback
import zmq
from logging import info

from .serializer import serializer


class RPCServer(object):
    """RPC server for invoking requests on proxied objects.
    
    Parameters
    ----------
    name : str
        Name used to identify this server.
    addr : URL
        Address for RPC server to bind to.
    """
    def __init__(self, name, addr):
        self._name = name.encode()
        self._socket = zmq.Context.instance().socket(zmq.ROUTER)
        self._socket.setsockopt(zmq.IDENTITY, self._name)
        self._socket.bind(addr)
        self._addr = self._socket.getsockopt(zmq.LAST_ENDPOINT)
        self._closed = False
        self._serializer = MsgpackSerializer(self)
        
        # Objects that may be retrieved by name using client['obj_name']
        self._namespace = {}
        
        # Objects for which we have sent proxies to other machines.
        self._proxies = {}  # obj_id: proxy
        
        info("RPC start server: %s@%s", self._name.decode(), self._addr.decode())

    def __del__(self):
        self._socket.close()
        
    def __getitem__(self, key):
        return self._namespace[key]

    def __setitem__(self, key, value):
        """Define an object that may be retrieved by name from the client.
        """
        self._namespace[key] = value

    def get_proxy(self, obj):
        """Create and return a new LocalObjectProxy for *obj*.
        """
        if id(obj) not in self._proxies:
            proxy = LocalObjectProxy(self.rpc_id, obj)
            self._proxies[id(obj)] = proxy
        return self._proxies[id(obj)]

    def lookup_proxy(self, proxy):
        """Return the object referenced by *proxy* if it belongs to this server.
        Otherwise, return the proxy.
        """
        if proxy.rpc_id == self.rpc_id:
            return self._proxies[proxy.obj_id]
        else:
            return proxy
        
    def _read_and_process_one(self):
        """Read one message from the rpc socket and invoke the requested
        action.
        """
        if not self.running:
            raise RuntimeError("RPC server socket is already closed.")
            
        name, msg = self._socket.recv_multipart()
        info("RPC recv req: %s %s", name, msg)
        
        self._process_one(name, msg)
        
    def _process_one(self, caller, msg):
        """
        Invoke the requested action.
        
        This method sends back to the client either the return value or an
        error message.
        """
        msg = self._serializer.loads(msg)
        action = msg['action']
        req_id = msg['req_id']
        return_type = msg.get('return_type', 'auto')
        opts = self._serializer.loads(msg['opts'])
        
        # Attempt to invoke requested action
        try:
            info("    handleRequest: id=%s opts=%s", req_id, opts)
            
            if cmd == 'get_obj_attr':
                result = getattr(opts['obj'], opts['attr'])
            elif cmd == 'call_obj':
                obj = opts['obj']
                fnargs = opts['args']
                fnkwds = opts['kwds']
                
                if len(fnkwds) == 0:  ## need to do this because some functions do not allow keyword arguments.
                    try:
                        result = obj(*fnargs)
                    except:
                        info("Failed to call object %s: %d, %s", obj, len(fnargs), fnargs[1:])
                        raise
                else:
                    result = obj(*fnargs, **fnkwds)
                    
            elif cmd == 'get_obj_value':
                result = opts['obj']  ## has already been unpickled into its local value
                return_type = 'value'
            elif cmd == 'transfer':
                result = opts['obj']
                return_type = 'proxy'
            elif cmd == 'import':
                name = opts['module']
                fromlist = opts.get('fromlist', [])
                mod = builtins.__import__(name, fromlist=fromlist)
                
                if len(fromlist) == 0:
                    parts = name.lstrip('.').split('.')
                    result = mod
                    for part in parts[1:]:
                        result = getattr(result, part)
                else:
                    result = map(mod.__getattr__, fromlist)
            elif cmd == 'del':
                LocalObjectProxy.releaseProxyId(opts['proxyId'])
                #del self.proxiedObjects[opts['objId']]
            elif cmd == 'close':
                result = True
            else:
                raise ValueError("Invalid RPC action '%s'" % cmd)
            exc = None
        except:
            exc = sys.exc_info()

            
        # Send result or error back to client
        if return_type is not None:
            if exc is None:
                self.debugMsg("    handleRequest: sending return value for %d: %s", req_id, result) 
                #print "returnValue:", returnValue, result
                if return_type == 'auto':
                    with self.optsLock:
                        noProxyTypes = self.proxyOptions['noProxyTypes']
                    result = self.autoProxy(result, noProxyTypes)
                elif return_type == 'proxy':
                    result = LocalObjectProxy(result)
                
                try:
                    self._send_result(caller, req_id, rval=result)
                except:
                    sys.excepthook(*sys.exc_info())
                    self._send_error(req_id, sys.exc_info())
            else:
                info("    handleRequest: returning exception for %d", req_id) 
                self._send_error(req_id, exc)
                    
        elif exc is not None:
            sys.excepthook(*exc)
    
        if cmd == 'close':
            self.close()
    
    def _send_error(self, caller, req_id, exc):
        exc_str = ["Error while processing request %s-%d: " % (caller, req_id)]
        exc_str += traceback.format_stack()
        exc_str += [" < exception caught here >\n"]
        exc = sys.exc_info()
        exc_str += traceback.format_exception(*exc)
        self._send_result(caller, req_id, error=(exc[0].__name__, exc_str))
    
    def _send_result(self, name, call_id, rval=None, error=None):
        result = {'action': 'return', 'call_id': call_id,
                  'rval': rval, 'error': error}
        info("RPC send res: %s %s", name, result)
        data = self._serializer.dumps(result)
        self._socket.send_multipart([name, data])

    def close(self):
        """Close this RPC server.
        """
        self._closed = True
        # keep the socket open just long enough to send a confirmation of
        # closure.

    def running(self):
        """Boolean indicating whether the server is still running.
        """
        return not self._closed
    
    def run_forever(self):
        while self.running():
            self._read_and_process_one()
