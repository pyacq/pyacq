import sys
import time
import traceback
import zmq
from logging import info

from .serializer import MsgpackSerializer
from .proxy import LocalObjectProxy, ObjectProxy


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
        self.address = self._socket.getsockopt(zmq.LAST_ENDPOINT)
        self._closed = False
        self._serializer = MsgpackSerializer(self)
        
        # Default behavior for creating object proxies
        self.proxy_options = {
            'call_sync': 'sync',      ## 'sync', 'async', 'off'
            'timeout': 10,            ## float
            'return_type': 'auto',    ## 'proxy', 'value', 'auto'
            'auto_proxy': False,      ## bool
            'defer_getattr': False,   ## True, False
            'no_proxy_types': [ type(None), str, int, float, tuple, list, dict, LocalObjectProxy, ObjectProxy ],
        }
        
        # Objects that may be retrieved by name using client['obj_name']
        self._namespace = {}
        
        # Objects for which we have sent proxies to other machines.
        self._proxies = {}  # obj_id: proxy
        
        info("RPC start server: %s@%s", self._name.decode(), self.address.decode())

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
            proxy = LocalObjectProxy(self.address, obj)
            self._proxies[id(obj)] = proxy
        return self._proxies[id(obj)]

    def lookup_proxy(self, proxy):
        """Return the object referenced by *proxy* if it belongs to this server.
        Otherwise, return the proxy.
        """
        if proxy.rpc_id == self.address:
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
            info("    process_one: id=%s opts=%s", req_id, opts)
            
            if action == 'get_obj_attr':
                result = getattr(opts['obj'], opts['attr'])
            elif action == 'call_obj':
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
                    
            elif action == 'get_obj_value':
                result = opts['obj']  ## has already been unpickled into its local value
                return_type = 'value'
            elif action == 'transfer':
                result = opts['obj']
                return_type = 'proxy'
            elif action == 'import':
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
            elif action == 'del':
                LocalObjectProxy.releaseProxyId(opts['proxyId'])
                #del self.proxiedObjects[opts['objId']]
            elif action == 'close':
                result = True
            elif action == 'ping':
                result = 'pong'
            elif action =='getitem':
                result = self[opts['name']]
            else:
                raise ValueError("Invalid RPC action '%s'" % action)
            exc = None
        except:
            exc = sys.exc_info()

            
        # Send result or error back to client
        if return_type is not None:
            if exc is None:
                info("    handleRequest: sending return value for %d: %s", req_id, result) 
                #print "returnValue:", returnValue, result
                if return_type == 'auto':
                    no_proxy_types = self.proxy_options['no_proxy_types']
                    result = self.auto_proxy(result, no_proxy_types)
                elif return_type == 'proxy':
                    result = LocalObjectProxy(result)
                
                try:
                    self._send_result(caller, req_id, rval=result)
                except:
                    info("    process_one: Failed to send result for %d", req_id) 
                    exc = sys.exc_info()
                    self._send_error(caller, req_id, exc)
            else:
                info("    process_one: returning exception for %d: %s", req_id, exc) 
                self._send_error(caller, req_id, exc)
                    
        elif exc is not None:
            sys.excepthook(*exc)
    
        if action == 'close':
            self.close()
    
    def _send_error(self, caller, req_id, exc):
        exc_str = ["Error while processing request %s-%d: " % (caller, req_id)]
        exc_str += traceback.format_stack()
        exc_str += [" < exception caught here >\n"]
        exc_str += traceback.format_exception(*exc)
        self._send_result(caller, req_id, error=(exc[0].__name__, exc_str))
    
    def _send_result(self, caller, req_id, rval=None, error=None):
        result = {'action': 'return', 'req_id': req_id,
                  'rval': rval, 'error': error}
        info("RPC send res: %s %s", caller, result)
        data = self._serializer.dumps(result)
        self._socket.send_multipart([caller, data])

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

    def auto_proxy(self, obj, no_proxy_types):
        ## Return object wrapped in LocalObjectProxy _unless_ its type is in noProxyTypes.
        for typ in no_proxy_types:
            if isinstance(obj, typ):
                return obj
        return LocalObjectProxy(obj)
