import sys
import time
import traceback
import zmq
import threading
import builtins
import numpy as np
from pyqtgraph.Qt import QtCore

from ..log import debug, info, warn, error
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
        self._closed_lock = threading.Lock()
        self._serializer = MsgpackSerializer(server=self)
        
        # types that are sent by value when return_type='auto'
        self.no_proxy_types = [type(None), str, int, float, tuple, list, dict, ObjectProxy, np.ndarray]
        
        # Objects that may be retrieved by name using client['obj_name']
        self._namespace = {'self': self}
        
        # Objects for which we have sent proxies to other machines.
        self.next_object_id = 0
        self._proxies = {}  # obj_id: object
        
        debug("RPC create server: %s@%s", self._name.decode(), self.address.decode())

    def get_proxy(self, obj, **kwds):
        """Return an ObjectProxy referring to a local object.
        
        This proxy can be sent via RPC to any other node.
        """
        oid = self.next_object_id
        self.next_object_id += 1
        type_str = str(type(obj))
        proxy = ObjectProxy(self.address, oid, type_str, attributes=(), **kwds)
        self._proxies[oid] = obj
        #debug("server %s add proxy %d: %s", self.address, oid, obj)
        return proxy
    
    def unwrap_proxy(self, proxy):
        """Return the local python object referenced by *proxy*.
        """
        try:
            oid = proxy._obj_id
            obj = self._proxies[oid]
            for attr in proxy._attributes:
                obj = getattr(obj, attr)
            #debug("server %s unwrap proxy %d: %s", self.address, oid, obj)
            return obj
        except KeyError:
            raise KeyError("Invalid proxy object ID %r. The object may have "
                           "been released already." % proxy.obj_id)

    #def __del__(self):
        #self._socket.close()
        
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
            debug("RPC recv '%s' from %s [req_id=%s]", action, caller.decode(), req_id)
            debug("    => %s", msg)
            opts = self._serializer.loads(opts)
            debug("    => opts: %s", opts)
            
            if action == 'call_obj':
                obj = opts['obj']
                fnargs = opts['args']
                fnkwds = opts['kwargs']
                
                if len(fnkwds) == 0:  ## need to do this because some functions do not allow keyword arguments.
                    try:
                        result = obj(*fnargs)
                    except:
                        warn("Failed to call object %s: %d, %s", obj, len(fnargs), fnargs[1:])
                        raise
                else:
                    result = obj(*fnargs, **fnkwds)
                #debug("    => call_obj result: %r", result)
            elif action == 'get_obj':
                result = opts['obj']
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
                #print "returnValue:", returnValue, result
                if return_type == 'auto':
                    result = self.auto_proxy(result, self.no_proxy_types)
                elif return_type == 'proxy':
                    result = self.get_proxy(result)
                
                try:
                    self._send_result(caller, req_id, rval=result)
                except:
                    warn("    => Failed to send result for %d", req_id) 
                    exc = sys.exc_info()
                    self._send_error(caller, req_id, exc)
            else:
                warn("    => returning exception for %d: %s", req_id, exc) 
                self._send_error(caller, req_id, exc)
                    
        elif exc is not None:
            sys.excepthook(*exc)
    
        if action == 'close':
            self.close()
    
    def _send_error(self, caller, req_id, exc):
        exc_str = ["Error while processing request %s [%d]: " % (caller.decode(), req_id)]
        exc_str += traceback.format_stack()
        exc_str += [" < exception caught here >\n"]
        exc_str += traceback.format_exception(*exc)
        self._send_result(caller, req_id, error=(exc[0].__name__, exc_str))
    
    def _send_result(self, caller, req_id, rval=None, error=None):
        result = {'action': 'return', 'req_id': req_id,
                  'rval': rval, 'error': error}
        debug("RPC send result to %s [rpc_id=%s]", caller.decode(), result['req_id'])
        debug("    => %s", result)
        data = self._serializer.dumps(result)
        self._socket.send_multipart([caller, data])

    def close(self):
        """Close this RPC server.
        """
        with self._closed_lock:
            self._closed = True
        # keep the socket open just long enough to send a confirmation of
        # closure.

    def running(self):
        """Boolean indicating whether the server is still running.
        """
        with self._closed_lock:
            return not self._closed
    
    def run_forever(self):
        info("RPC start server: %s@%s", self._name.decode(), self.address.decode())
        RPCServer.register_server(self)
        while self.running():
            self._read_and_process_one()

    def auto_proxy(self, obj, no_proxy_types):
        ## Return object wrapped in LocalObjectProxy _unless_ its type is in noProxyTypes.
        for typ in no_proxy_types:
            if isinstance(obj, typ):
                return obj
        return self.get_proxy(obj)



class QtRPCServer(RPCServer):
    def __init__(self, name, addr):
        RPCServer.__init__(self, name, addr)
        self.poll_thread = QtPollThread(self)
        
    def run_forever(self):
        info("RPC start server: %s@%s", self._name.decode(), self.address.decode())
        RPCServer.register_server(self)
        self.poll_thread.start()

    def _read_and_process_one(self):
        raise NotImplementedError('Socket reading is handled by poller thread.')


class QtPollThread(QtCore.QThread):
    """Thread that polls an RPCServer socket and sends incoming messages to the
    server by Qt signal.
    
    This allows the RPC actions to be executed in a Qt GUI thread without using
    a timer to poll the RPC socket. Responses are sent back to the poller
    thread by a secondary socket.
    """
    new_request = QtCore.Signal(object, object)  # client, msg
    
    def __init__(self, server):
        QtCore.QThread.__init__(self)
        self.server = server
        
        # Steal RPC socket from the server; it should not be touched outside the
        # polling thread.
        self.rpc_socket = server._socket
        
        # Create a socket for the Qt thread to send results back to the poller
        # thread
        return_addr = 'inproc://%x' % id(self)
        context = zmq.Context.instance()
        self.return_socket = context.socket(zmq.PAIR)
        self.return_socket.bind(return_addr)
        
        server._socket = context.socket(zmq.PAIR)
        server._socket.connect(return_addr)

        self.new_request.connect(server._process_one)
        
    def run(self):
        poller = zmq.Poller()
        poller.register(self.rpc_socket, zmq.POLLIN)
        poller.register(self.return_socket, zmq.POLLIN)
        
        while self.server.running():
            #with self.lock:
                #if not self.running:
                    ## do a last poll
                    #socks = dict(self.poller.poll(timeout=500))
                    #if len(socks)==0:
                        #self.local_socket.close()
                        #break
            
            socks = dict(poller.poll(timeout=100))
            
            if self.return_socket in socks:
                name, data = self.return_socket.recv_multipart()
                self.rpc_socket.send_multipart([name, data])
                
            if self.rpc_socket in socks:
                name, msg = self.rpc_socket.recv_multipart()
                self.new_request.emit(name, msg)
