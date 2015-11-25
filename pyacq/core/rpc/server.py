import sys
import time
import os
import traceback
import socket
import threading
import builtins
import zmq
import logging
import numpy as np
import atexit
from pyqtgraph.Qt import QtCore, QtGui

from .serializer import all_serializers
from .proxy import ObjectProxy
from . import log


logger = logging.getLogger(__name__)


class RPCServer(object):
    """RPC server for invoking requests on proxied objects.
    
    Parameters
    ----------
    name : str
        Name used to identify this server.
    addr : URL
        Address for RPC server to bind to.

    Basic usage::
    
        # In host/process/thread 1:
        server = RPCServer()
        rpc_addr = server.address

        # Publish an object for others to access easily
        server['object_name'] = MyClass()
        
        
        # In host/process/thread 2: (you must communicate rpc_addr manually)
        client = RPCClient(rpc_addr)
        
        # Get a proxy to published object; use this (almost) exactly as you
        # would a local object:
        remote_obj = client['object_name']
        remote_obj.method(...)
        
        # Or, you can remotely import and operate a module:
        remote_module = client._import("my.module.name")
        remote_obj = remote_module.MyClass()
        remote_obj.method(...)
        
        # See ObjectProxy for more information on interacting with remote
        # objects, including (a)synchronous communication.

    There may be at most one RPCServer per thread. RPCServers can be run in a
    few different modes:
    
    * Exclusive event loop - call `run_forever()` to cause the server to listen
      indefinitely for incoming request messages.
    * Lazy event loop - call `run_lazy()` to register the server with the current
      thread. The server's socket will be polled whenever an RPCClient is waiting
      for a response (this allows reentrant function calls). You can also manually
      listen for requests with `_read_and_process_one()` in this mode.
    * Qt event loop - use QtRPCServer. In this mode, messages are polled in 
      a separate thread, but then sent to the Qt event loop by signal and
      processed there. The server is registered as running in the Qt thread.
        
    Note: RPCServer is not a thread-safe class. Only use RPCClient to communicate
    with RPCServer from other threads.
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
        """Register a server as the (only) server running in this thread.
        
        This static method fails if another server is already registered for
        this thread.
        """
        assert srv._thread is None, "Server has already been registered."
        key = threading.current_thread().ident
        with RPCServer.servers_by_thread_lock:
            if key in RPCServer.servers_by_thread:
                raise KeyError("An RPCServer is already running in this thread.")
            RPCServer.servers_by_thread[key] = srv
        srv._thread = key

    @staticmethod
    def unregister_server(srv):
        """Unregister a server from this thread.
        """
        key = srv._thread
        with RPCServer.servers_by_thread_lock:
            assert RPCServer.servers_by_thread[key] is srv
            RPCServer.servers_by_thread.pop(key)

    @staticmethod
    def local_client():
        """Return the RPCClient used for accessing the server running in the
        current thread.
        """
        from .client import RPCClient
        srv = RPCServer.get_server()
        return RPCClient.get_client(srv.address)
        
    def __init__(self, addr="tcp://*:*"):
        self._socket = zmq.Context.instance().socket(zmq.ROUTER)
        
        # socket will continue attempting to deliver messages up to 5 sec after
        # it has closed. (default is -1, which can cause processes to hang
        # on exit)
        self._socket.linger = 5000
        
        self._socket.bind(addr)
        self.address = self._socket.getsockopt(zmq.LAST_ENDPOINT)
        self._closed = False
        
        # Clients may make requests using any supported serializer, so we should
        # have one of each ready.
        self._serializers = {}
        for ser in all_serializers.values():
            self._serializers[ser.type] = ser(server=self)
        
        # keep track of all clients we have seen so that we can inform them 
        # when the server exits.
        self._clients = {}  # {socket_id: serializer_type}
        
        # Id of thread that this server is registered to
        self._thread = None
        
        # types that are sent by value when return_type='auto'
        self.no_proxy_types = [type(None), str, int, float, tuple, list, dict, ObjectProxy, np.ndarray]
        
        # Objects that may be retrieved by name using client['obj_name']
        self._namespace = {'self': self}
        
        # Objects for which we have sent proxies to other machines.
        self.next_object_id = 0
        self._proxies = {}  # obj_id: object
        
        # Make sure we inform clients of closure
        atexit.register(self._atexit)

    def get_proxy(self, obj, **kwds):
        """Return an ObjectProxy referring to a local object.
        
        This proxy can be sent via RPC to any other node.
        """
        oid = self.next_object_id
        self.next_object_id += 1
        type_str = str(type(obj))
        proxy = ObjectProxy(self.address, oid, type_str, attributes=(), **kwds)
        self._proxies[oid] = obj
        #logging.debug("server %s add proxy %d: %s", self.address, oid, obj)
        return proxy
    
    def unwrap_proxy(self, proxy):
        """Return the local python object referenced by *proxy*.
        """
        try:
            oid = proxy._obj_id
            obj = self._proxies[oid]
            for attr in proxy._attributes:
                obj = getattr(obj, attr)
            #logging.debug("server %s unwrap proxy %d: %s", self.address, oid, obj)
            return obj
        except KeyError:
            raise KeyError("Invalid proxy object ID %r. The object may have "
                           "been released already." % proxy.obj_id)

    def __getitem__(self, key):
        return self._namespace[key]

    def __setitem__(self, key, value):
        """Define an object that may be retrieved by name from the client.
        """
        self._namespace[key] = value
        
    @staticmethod
    def _read_one(socket):
        name, req_id, action, return_type, ser_type, opts = socket.recv_multipart()
        msg = {
            'req_id': int(req_id), 
            'action': action.decode(), 
            'return_type': return_type.decode(),
            'ser_type': ser_type.decode(),
            'opts': opts,
        }
        return name, msg
        
    def _read_and_process_one(self):
        """Read one message from the rpc socket and invoke the requested
        action.
        """
        if not self.running:
            raise RuntimeError("RPC server socket is already closed.")
            
        name, msg = self._read_one(self._socket)
        self._process_one(name, msg)
        
    def _process_one(self, caller, msg):
        """
        Invoke the requested action.
        
        This method sends back to the client either the return value or an
        error message.
        """
        ser_type = msg['ser_type']
        action = msg['action']
        req_id = msg['req_id']
        return_type = msg.get('return_type', 'auto')
        
        # remember this caller so we can deliver a disconnect message later
        self._clients[caller] = ser_type
        
        # Attempt to read message and invoke requested action
        try:
            try:
                serializer = self._serializers[ser_type]
            except KeyError:
                raise ValueError("Unsupported serializer '%s'" % ser_type)
            opts = msg.pop('opts', None)
            
            logging.debug("RPC recv '%s' from %s [req_id=%s]", action, caller.decode(), req_id)
            logging.debug("    => %s", msg)
            if opts == b'':
                opts = None
            else:
                opts = serializer.loads(opts)
            logging.debug("    => opts: %s", opts)
            
            result = self.process_action(action, opts, return_type, caller)
            exc = None
        except:
            exc = sys.exc_info()

        # Send result or error back to client
        if req_id >= 0:
            if exc is None:
                #print "returnValue:", returnValue, result
                if return_type == 'auto':
                    result = self.auto_proxy(result, self.no_proxy_types)
                elif return_type == 'proxy':
                    result = self.get_proxy(result)
                
                try:
                    self._send_result(caller, req_id, rval=result)
                except:
                    logger.warn("    => Failed to send result for %d", req_id) 
                    exc = sys.exc_info()
                    self._send_error(caller, req_id, exc)
            else:
                logger.warn("    => returning exception for %d: %s", req_id, exc) 
                self._send_error(caller, req_id, exc)
                    
        elif exc is not None:
            # An exception occurred, but client did not request a response.
            # Instead we will dump the exception here.
            sys.excepthook(*exc)
            
        if action == 'close':
            self._final_close()
    
    def _send_error(self, caller, req_id, exc):
        exc_str = ["Error while processing request %s [%d]: " % (caller.decode(), req_id)]
        exc_str += traceback.format_stack()
        exc_str += [" < exception caught here >\n"]
        exc_str += traceback.format_exception(*exc)
        self._send_result(caller, req_id, error=(exc[0].__name__, exc_str))
    
    def _send_result(self, caller, req_id, rval=None, error=None):
        result = {'action': 'return', 'req_id': req_id,
                  'rval': rval, 'error': error}
        logging.debug("RPC send result to %s [rpc_id=%s]", caller.decode(), result['req_id'])
        logging.debug("    => %s", result)
        
        # Select the correct serializer for this client
        serializer = self._serializers[self._clients[caller]]
        
        # Serialize and return the result
        data = serializer.dumps(result)
        self._socket.send_multipart([caller, data])

    def process_action(self, action, opts, return_type, caller):
        """Invoke a single action and return the result.
        """
        if action == 'call_obj':
            obj = opts['obj']
            fnargs = opts['args']
            fnkwds = opts['kwargs']
            
            if len(fnkwds) == 0:  ## need to do this because some functions do not allow keyword arguments.
                try:
                    result = obj(*fnargs)
                except:
                    logger.warn("Failed to call object %s: %d, %s", obj, len(fnargs), fnargs[1:])
                    raise
            else:
                result = obj(*fnargs, **fnkwds)
            #logging.debug("    => call_obj result: %r", result)
        elif action == 'get_obj':
            result = opts['obj']
        elif action == 'delete':
            del self._proxies[opts['obj_id']]
            result = None
        elif action =='getitem':
            result = self[opts['name']]
        elif action =='setitem':
            self[opts['name']] = opts['obj']
            result = None
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
        elif action == 'ping':
            result = 'pong'
        elif action == 'close':
            self._closed = True
            # Send a disconnect message to all known clients
            data = {}
            for client, ser_type in self._clients.items():
                if client == caller:
                    # We will send an actual return value to confirm closure
                    # to the caller.
                    continue
                
                # Select or generate the disconnect message that was serialized
                # correctly for this client.
                if ser_type not in data:
                    ser = self._serializers[ser_type]
                    data[ser_type] = ser.dumps({'action': 'disconnect'})
                data_str = data[ser_type]
                
                # Send disconnect message.
                logger.debug("RPC server sending disconnect message to %r", client)
                self._socket.send_multipart([client, data_str])
            RPCServer.unregister_server(self)
            result = True
        else:
            raise ValueError("Invalid RPC action '%s'" % action)
        
        return result

    def _atexit(self):
        # Process is exiting; do any last-minute cleanup if necessary.
        if self._closed is not True:
            logger.warn("RPCServer exiting without close()!")
            self.close()

    def close(self):
        """Ask the server to close.
        
        This method is thread-safe.
        """
        from .client import RPCClient
        cli = RPCClient.get_client(self.address)
        if cli is None:
            self.process_action('close', None, None, None)
        else:
            cli.close_server(sync='sync')

    def _final_close(self):
        # Called after the server has closed and sent its disconnect messages.
        pass

    def running(self):
        """Boolean indicating whether the server is still running.
        """
        return self._closed is False
    
    def run_forever(self):
        """Read and process RPC requests until the server is asked to close.
        """
        name = ('%s.%s.%s' % (log.get_host_name(), log.get_process_name(), 
                              log.get_thread_name()))

        logging.info("RPC start server: %s@%s", name, self.address.decode())
        RPCServer.register_server(self)
        while self.running():
            name, msg = self._read_one(self._socket)
            self._process_one(name, msg)
            
    def run_lazy(self):
        """Register this server as being active for the current thread, but do
        not actually begin processing requests.
        
        RPCClients in the same thread will allow the server to process requests
        while they are waiting for responses. This can prevent deadlocks that
        occur when 
        
        This can also be used to allow the user to manually process requests.
        """
        name = ('%s.%s.%s' % (log.get_host_name(), log.get_process_name(), 
                              log.get_thread_name()))
        logging.info("RPC lazy-start server: %s@%s", name, self.address.decode())
        RPCServer.register_server(self)

    def auto_proxy(self, obj, no_proxy_types):
        ## Return object wrapped in LocalObjectProxy _unless_ its type is in noProxyTypes.
        for typ in no_proxy_types:
            if isinstance(obj, typ):
                return obj
        return self.get_proxy(obj)


class QtRPCServer(RPCServer):
    """RPCServer that lives in a Qt GUI thread.
    
    This server may be used to create and manage QObjects, QWidgets, etc. It
    uses a separate thread to poll for RPC requests, which are then sent to the
    Qt event loop using by signal (see QtPollThread).
    
    Parameters
    ----------
    addr : str
        ZMQ address to listen on. Default is "tcp://*:*".
    quit_on_close : bool
        If True, then call `QApplication.quit()` when the server is closed. 
    """
    def __init__(self, addr="tcp://*:*", quit_on_close=True):
        RPCServer.__init__(self, addr)
        self.quit_on_close = quit_on_close
        self.poll_thread = QtPollThread(self)
        
    def run_forever(self):
        name = ('%s.%s.%s' % (log.get_host_name(), log.get_process_name(), 
                              log.get_thread_name()))
        logging.info("RPC start server: %s@%s", name, self.address.decode())
        RPCServer.register_server(self)
        self.poll_thread.start()

    def process_action(self, action, opts, return_type, caller):
        # this method is called from the Qt main thread.
        if action == 'close':
            if self.quit_on_close:
                QtGui.QApplication.instance().quit()
            # can't stop poller thread here--that would prevent the return 
            # message being sent. In general it should be safe to leave this thread
            # running anyway.
            #self.poll_thread.stop()
        return RPCServer.process_action(self, action, opts, return_type, caller)

    def _final_close(self):
        # Block for a moment to allow the poller thread to flush any pending
        # messages. Ideally, we could let the poller thread keep the process
        # alive until it is done, but then we can end up with zombie processes..
        time.sleep(0.1)


class QtPollThread(QtCore.QThread):
    """Thread that polls an RPCServer socket and sends incoming messages to the
    server by Qt signal.
    
    This allows the RPC actions to be executed in a Qt GUI thread without using
    a timer to poll the RPC socket. Responses are sent back to the poller
    thread by a secondary socket.
    """
    new_request = QtCore.Signal(object, object)  # client, msg
    
    def __init__(self, server):
        # Note: QThread behaves like threading.Thread(daemon=True); a running
        # QThread will not prevent the process from exiting.
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
        
        while True:
            # Note: poller needs to continue running until server has sent 
            # its final response (which can be after the server claims to be
            # no longer running).
            socks = dict(poller.poll(timeout=100))
            
            if self.return_socket in socks:
                name, data = self.return_socket.recv_multipart()
                #logger.debug("poller return %s %s", name, data)
                if name == 'STOP':
                    break
                self.rpc_socket.send_multipart([name, data])
                
            if self.rpc_socket in socks:
                name, msg = RPCServer._read_one(self.rpc_socket)
                #logger.debug("poller recv %s %s", name, msg)
                self.new_request.emit(name, msg)

        #logger.error("poller exit.")
        
    def stop(self):
        """Ask the poller thread to stop.
        
        This method may only be called from the Qt main thread.
        """
        self.server._socket.send_multipart([b'STOP', b''])
