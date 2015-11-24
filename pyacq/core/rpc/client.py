import os
import time
import weakref
import socket
import concurrent.futures
import threading
import zmq
import logging
import numpy as np
from pyqtgraph.Qt import QtGui

from .serializer import all_serializers
from .proxy import ObjectProxy
from .server import RPCServer, QtRPCServer
from . import log


logger = logging.getLogger(__name__)


class RPCClient(object):
    """Connection to an RPC server.
    
    Parameters
    ----------
    address : URL
        Address of RPC server to connect to.
    reentrant : bool
        If True, then this client will allow the server running in the same 
        thread (if any) to process requests whenever the client is waiting
        for a response. This is necessary to avoid deadlocks in case of 
        reentrant RPC requests (eg, server A calls server B, which then calls
        server A again). Default is True.
    """
    
    clients_by_thread = {}  # (thread_id, rpc_addr): client
    clients_by_thread_lock = threading.Lock()
    
    @staticmethod
    def get_client(address):
        """Return the RPC client for this thread and a given server address.
        
        If no client exists already, then a new one will be created. If the 
        server is running in the current thread, then return None.
        """
        if isinstance(address, str):
            address = address.encode()
        key = (threading.current_thread().ident, address)
        
        # Return an existing client if there is one
        with RPCClient.clients_by_thread_lock:
            if key in RPCClient.clients_by_thread:
                return RPCClient.clients_by_thread[key]
        
        return RPCClient(address)
    
    def __init__(self, address, reentrant=True, serializer='msgpack'):
        # pick a unique name: host.pid.tid:rpc_addr
        self.name = ("%s.%s.%s:%s" % (log.get_host_name(), log.get_process_name(),
                                      log.get_thread_name(), address.decode())).encode()
        self.address = address
        
        key = (threading.current_thread().ident, address)
        with RPCClient.clients_by_thread_lock:
            if key in RPCClient.clients_by_thread:
                raise KeyError("An RPCClient instance already exists for this address."
                    " Use RPCClient.get_client(address) instead.")
        
        # ROUTER is fully asynchronous and may connect to multiple endpoints.
        # We can use ROUTER to allow this socket to connect to multiple servers.
        # However this adds complexity with little benefit, as we can just use
        # a poller to check for messages on multiple sockets if desired.
        #self._socket = zmq.Context.instance().socket(zmq.ROUTER)
        #self._name = ('%d-%x' % (os.getpid(), id(self))).encode()
        #self._socket.setsockopt(zmq.IDENTITY, self._name)
        
        # DEALER is fully asynchronous--we can send or receive at any time, and
        # unlike ROUTER, it only connects to a single endpoint.
        self._socket = zmq.Context.instance().socket(zmq.DEALER)
        self._sock_name = self.name
        self._socket.setsockopt(zmq.IDENTITY, self._sock_name)
        
        # If this thread is running a server, then we need to allow the 
        # server to process requests when the client is blocking.
        assert reentrant in (None, True, False)
        server = RPCServer.get_server()
        if reentrant is True and server is not None:
            if isinstance(server, QtRPCServer):
                self._poller = 'qt'
                self._reentrant = True
            else:
                self._poller = zmq.Poller()
                self._poller.register(self._socket, zmq.POLLIN)
                self._poller.register(server._socket, zmq.POLLIN)
                self._reentrant = True
        else:
            self._poller = None
            self._reentrant = False
        
        logger.info("RPC connect to %s", address.decode())
        self._socket.connect(address)
        self.next_request_id = 0
        self.futures = weakref.WeakValueDictionary()
        
        with RPCClient.clients_by_thread_lock:
            RPCClient.clients_by_thread[key] = self
        
        # proxies generated by this client will be assigned these default options
        self.default_proxy_options = {}
        
        self.connect_established = False
        self.establishing_connect = False
        self._disconnected = False

        # Proxies we have received from other machines. 
        self.proxies = {}

        # For unserializing results returned from servers. This cannot be
        # used to send proxies of local objects unless there is also a server
        # for this thread..
        try:
            self.serializer = all_serializers[serializer](client=self)
        except KeyError:
            raise ValueError("Unsupported serializer type '%s'" % serializer)
        
        self.ensure_connection()

    def disconnected(self):
        """Boolean indicating whether the server has disconnected from the client.
        """
        if self._disconnected:
            return True
        
        # check to see if we have received any new messages
        self._read_and_process_all()
        return self._disconnected

    def send(self, action, opts=None, return_type='auto', sync='sync', timeout=10.0):
        """Send a request to the remote process.
        
        Parameters
        ----------
        action : str
            The action to invoke on the remote process.
        opts : None or dict
            Extra options to be sent with the request. Each action requires a
            different set of options.
        return_type : 'auto' | 'proxy'
            If 'proxy', then the return value is sent by proxy. If 'auto', then
            the server decides based on the return type whether to send a proxy.
        sync : str
            If 'sync', then block and return the result when it becomes available.
            If 'async', then return a Future instance immediately.
            If 'off', then ask the remote server NOT to send a response and
            return None immediately.
        timeout : float
            The amount of time to wait for a response when in synchronous
            operation (sync='sync').
        """
        if self.disconnected():
            raise RuntimeError("Cannot send request; server has already disconnected.")
        cmd = {'action': action, 'return_type': return_type, 
               'opts': opts}
        if sync == 'off':
            req_id = None
        else:
            req_id = self.next_request_id
            self.next_request_id += 1
        cmd['req_id'] = req_id
        logger.info("RPC request '%s' to %s [req_id=%s]", cmd['action'], 
                    self.address.decode(), req_id)
        logger.debug("    => %s", cmd)
        
        # double-serialize opts to ensure that cmd can be read even if opts
        # cannot.
        # TODO: This might be expensive; a better way might be to send opts in
        # a subsequent packet, but this makes the protocol more complicated..
        if cmd['opts'] is not None:
            cmd = cmd.copy()  # because logger might format old dict later on..
            cmd['opts'] = self.serializer.dumps(cmd['opts'])
        cmd = self.serializer.dumps(cmd)
        
        self._socket.send_multipart([self.serializer.type.encode(), cmd])
        
        # If using ROUTER, we have to include the name of the endpoint to which
        # we are sending
        #self._socket.send_multipart([name, cmd])
        
        if sync == 'off':
            return
        
        fut = Future(self, req_id)
        if action == 'close':
            # for server closure we require a little special handling
            fut.add_done_callback(self._close_request_returned)
        self.futures[req_id] = fut
        
        if sync == 'async':
            return fut
        elif sync == 'sync':
            return fut.result(timeout=timeout)
        else:
            raise ValueError('Invalid sync value: %s' % sync)

    def call_obj(self, obj, args=None, kwargs=None, **kwds):
        opts = {'obj': obj, 'args': args, 'kwargs': kwargs} 
        return self.send('call_obj', opts=opts, **kwds)

    def get_obj(self, obj, **kwds):
        return self.send('get_obj', opts={'obj': obj}, **kwds)

    def transfer(self, obj, **kwds):
        kwds['return_type'] = 'proxy'
        return self.send('get_obj', opts={'obj': obj}, **kwds)

    def _import(self, module, **kwds):
        return self.send('import', opts={'module': module}, **kwds)

    def delete(self, obj, **kwds):
        assert obj._rpc_addr == self.address
        return self.send('delete', opts={'obj_id': obj._obj_id}, **kwds)

    def __getitem__(self, name):
        return self.send('getitem', opts={'name': name}, sync='sync')

    def __setitem__(self, name, obj):
        # We could make this sync='off', but probably it's safer to block until
        # the transaction is complete.
        return self.send('setitem', opts={'name': name, 'obj': obj}, sync='sync')

    def ensure_connection(self, timeout=1.0):
        """Make sure RPC server is connected and available.
        """
        if self.establishing_connect:
            return
        self.establishing_connect = True
        try:
            start = time.time()
            while time.time() < start + timeout:
                fut = self.ping(sync='async')
                try:
                    result = fut.result(timeout=0.1)
                    self.connect_established = True
                    return
                except TimeoutError:
                    continue
            raise TimeoutError("Could not establish connection with RPC server.")
        finally:
            self.establishing_connect = False

    def process_until_future(self, future, timeout=None):
        """Process all incoming messages until receiving a result for *future*.
        
        If the future result is not raised before the timeout, then raise
        TimeoutError.
        
        While waiting, the RPCServer for this thread (if any) is also allowed to process
        requests.
        """
        start = time.perf_counter()
        while not future.done():
            # wait patiently with blocking calls.
            if timeout is None:
                itimeout = None
            else:
                dt = time.perf_counter() - start
                itimeout = timeout - dt
                if itimeout < 0:
                    raise TimeoutError("Timeout waiting for Future result.")
                
            if self._poller is None:
                self._read_and_process_one(itimeout)
            elif self._poller == 'qt':
                # Server runs in Qt thread; we need to time-share with Qt event
                # loop.
                QtGui.QApplication.processEvents()
                try:
                    self._read_and_process_one(timeout=0.05)
                except TimeoutError:
                    pass
            else:
                # Poll for input on both the client's socket and the server's
                # socket. This is necessary to avoid deadlocks.
                socks = [x[0] for x in self._poller.poll(itimeout)]
                if self._socket in socks:
                    self._read_and_process_one(timeout=0)
                elif len(socks) > 0: 
                    server = RPCServer.get_server()
                    server._read_and_process_one()
                
    def _read_and_process_one(self, timeout):
        # timeout is in seconds; convert to ms
        # use timeout=None to block indefinitely
        if timeout is None:
            timeout = -1
        else:
            timeout = int(timeout * 1000)
        
        try:
            # NOTE: docs say timeout can only be set before bind, but this
            # seems to work for now.
            self._socket.setsockopt(zmq.RCVTIMEO, timeout)
            msg = self._socket.recv()
            msg = self.serializer.loads(msg)
        except zmq.error.Again:
            raise TimeoutError("Timeout waiting for Future result.")
        
        self.process_msg(msg)

    def _read_and_process_all(self):
        # process all messages until none are immediately available.
        try:
            while True:
                self._read_and_process_one(timeout=0)
        except TimeoutError:
            return

    def process_msg(self, msg):
        """Handle one message received from the remote process.
        
        This takes care of assigning return values or exceptions to existing
        Future instances.
        """
        logger.debug("RPC recv result from %s [req_id=%s]", self.address.decode(), 
                     msg.get('req_id', None))
        logger.debug("    => %s" % msg)
        if msg['action'] == 'return':
            req_id = msg['req_id']
            fut = self.futures.pop(req_id, None)
            if fut is None:
                return
            if msg['error'] is not None:
                exc = RemoteCallException(*msg['error'])
                fut.set_exception(exc)
            else:
                fut.set_result(msg['rval'])
        elif msg['action'] == 'disconnect':
            self._server_disconnected()
        else:
            raise ValueError("Invalid action '%s'" % msg['action'])

    def _close_request_returned(self, fut):
        try:
            if fut.result() is True:
                # We requested a server closure and the server complied; now
                # handle the disconnect.
                self._server_disconnected()
        except RuntimeError:
            # might have already disconnected before this request finished.
            if self.disconnected():
                pass
            raise
    
    def _server_disconnected(self):
        # server has disconnected; inform all pending futures.
        # This method can be called two different ways:
        # * this client requested that the server close and it returned True
        # * another client requested that the server close and this client
        #   received a preemptive disconnect message from the server.
        self._disconnected = True
        logger.debug("Received server disconnect from %s", self.address)
        exc = RuntimeError("Cannot send request; server has already disconnected.")
        for fut in self.futures.values():
            fut.set_exception(exc)
        self.futures.clear()
    
    def ping(self, sync='sync', **kwds):
        """Ping the server.
        
        This can be used to test connectivity to the server.
        """
        return self.send('ping', sync=sync, **kwds)        
    
    def close(self):
        """Close this client's socket (but leave the server running).
        """
        # reference management is disabled for now..
        #self.send('release_all', return_type=None) 
        self._socket.close()

    def close_server(self, sync='sync', **kwds):
        """Ask the server to close.
        
        The server returns True if it has closed. All clients known to the
        server will be informed that the server has disconnected.
        
        If the server has already disconnected from this client, then the
        method returns True without error.
        """
        if self.disconnected():
            return True
        return self.send('close', sync=sync, **kwds)

    def measure_clock_diff(self):
        rcounter = self._import('time').perf_counter
        ltimes = []
        rtimes = []
        for i in range(10):
            ltimes.append(time.perf_counter())
            rtimes.append(rcounter())
        ltimes = np.array(ltimes)
        rtimes = np.array(rtimes[:-1])
        dif = rtimes - ((ltimes[1:] + ltimes[:-1]) * 0.5)
        # we can probably constrain this estimate a bit more by looking at
        # min/max times and excluding outliers.
        return dif.mean()

    def __del__(self):
        if hasattr(self, 'socket'):
            self.close()
        


class RemoteCallException(Exception):
    def __init__(self, type_str, tb_str):
        self.type_str = type_str
        self.tb_str = tb_str
        
    def __str__(self):
        msg = '\n===> Remote exception was:\n' + ''.join(self.tb_str)
        return msg


class Future(concurrent.futures.Future):
    """Represents a return value from a remote procedure call that has not
    yet arrived.
    
    Use `done()` to determine whether the return value (or an error message)
    has arrived, and `result()` to get the return value (or raise an
    exception).
    """
    def __init__(self, client, call_id):
        concurrent.futures.Future.__init__(self)
        self.client = client
        self.call_id = call_id
    
    def cancel(self):
        return False

    def result(self, timeout=None):
        """Return the result of this Future.
        
        If the result is not yet available, then this call will block until
        the result has arrived or the timeout elapses.
        """
        self.client.process_until_future(self, timeout=timeout)
        return concurrent.futures.Future.result(self)
