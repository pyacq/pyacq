import sys
import time
import traceback
import zmq
import threading
from logging import info

from .serializer import MsgpackSerializer
from .proxy import ObjectProxy


class RPCServer(object):
    """RPC server for invoking requests on proxied objects.
    
    Parameters
    ----------
    name : str
        Name used to identify this server.
    addr : URL
        Address for RPC server to bind to.
    """
    
    servers_by_thread = {}
    servers_by_thread_lock = threading.Lock()
    
    @staticmethod
    def get_server():
        """Return the server running in this thread, or None if there is no server.
        """
        with RPCServer.servers_by_thread_lock:
            return RPCServer.servers_by_thread.get(threading.current_thread().ident, None)
    
    @staticmethod
    def register_server(srv):
        with RPCServer.servers_by_thread_lock:
            key = threading.current_thread().ident
            if key in RPCServer.servers_by_thread:
                raise KeyError("An RPCServer is already running in this thread.")
            RPCServer.servers_by_thread[key] = srv
        
    def __init__(self, name, addr):
        self._name = name.encode()
        self._socket = zmq.Context.instance().socket(zmq.ROUTER)
        self._socket.setsockopt(zmq.IDENTITY, self._name)
        self._socket.bind(addr)
        self.address = self._socket.getsockopt(zmq.LAST_ENDPOINT)
        self._closed = False
        self._serializer = MsgpackSerializer(self)
        
        # types that are sent by value when return_type='auto'
        self.no_proxy_types = [type(None), str, int, float, tuple, list, dict, ObjectProxy]
        
        # Objects that may be retrieved by name using client['obj_name']
        self._namespace = {'self': self}
        
        # Objects for which we have sent proxies to other machines.
        self.next_object_id = 0
        self._proxies = {}  # obj_id: object
        
        info("RPC start server: %s@%s", self._name.decode(), self.address.decode())

    def get_proxy(self, obj, **kwds):
        """Return an ObjectProxy referring to a local object.
        
        This proxy can be sent via RPC to any other node.
        """
        oid = self.next_object_id
        self.next_object_id += 1
        type_str = str(type(obj))
        proxy = ObjectProxy(self.address, oid, type_str, attributes=(), **kwds)
        self._proxies[oid] = obj
        info("server %s add proxy %d: %s", self.address, oid, obj)
        return proxy
    
    def unwrap_proxy(self, proxy):
        """Return the local python object referenced by *proxy*.
        """
        try:
            oid = proxy._obj_id
            obj = self._proxies[oid]
            for attr in proxy._attributes:
                obj = getattr(obj, attr)
            info("server %s unwrap proxy %d: %s", self.address, oid, obj)
            return obj
        except KeyError:
            raise KeyError("Invalid proxy object ID %r. The object may have "
                           "been released already." % proxy.obj_id)

    def __del__(self):
        self._socket.close()
        
    def __getitem__(self, key):
        return self._namespace[key]

    def __setitem__(self, key, value):
        """Define an object that may be retrieved by name from the client.
        """
        self._namespace[key] = value

    #def get_proxy(self, obj):
        #"""Create and return a new LocalObjectProxy for *obj*.
        #"""
        #if id(obj) not in self._proxies:
            #proxy = LocalObjectProxy(self, obj)
            #self._proxies[id(obj)] = proxy
        #return self._proxies[id(obj)]

    #def lookup_proxy(self, proxy):
        #"""Return the object referenced by *proxy* if it belongs to this server.
        #Otherwise, return the proxy.
        #"""
        #if proxy.rpc_id == self.address:
            #obj = self._proxies[proxy.obj_id]
            ## handle any deferred attribute lookups
            #for attr in obj.attributes:
                #obj = getattr(obj, attr)
            #return obj
        #else:
            #return proxy
        
    def _read_and_process_one(self):
        """Read one message from the rpc socket and invoke the requested
        action.
        """
        if not self.running:
            raise RuntimeError("RPC server socket is already closed.")
            
        name, msg = self._socket.recv_multipart()
        
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
        opts = msg.pop('opts')
        
        # Attempt to invoke requested action
        try:
            info("RPC recv from %s request: %s", caller, msg)
            opts = self._serializer.loads(opts)
            info("    request opts: %s", opts)
            
            if action == 'call_obj':
                obj = opts['obj']
                fnargs = opts['args']
                fnkwds = opts['kwargs']
                
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
                del self.proxies[opts['obj_id']]
                #LocalObjectProxy.releaseProxyId(opts['proxyId'])
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
        if req_id is not None:
            if exc is None:
                info("    handleRequest: sending return value for %d: %s", req_id, result) 
                #print "returnValue:", returnValue, result
                if return_type == 'auto':
                    result = self.auto_proxy(result, self.no_proxy_types)
                elif return_type == 'proxy':
                    result = self.get_proxy(result)
                
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
        RPCServer.register_server(self)
        while self.running():
            self._read_and_process_one()

    def auto_proxy(self, obj, no_proxy_types):
        ## Return object wrapped in LocalObjectProxy _unless_ its type is in noProxyTypes.
        for typ in no_proxy_types:
            if isinstance(obj, typ):
                return obj
        return self.get_proxy(obj)
