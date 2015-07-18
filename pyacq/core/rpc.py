"""
RPC implemented over zmq sockets.

- remote procedure calls can be synchronous, asynchronous, or no-return
- exceptions propagate nicely back to caller
- no specific event loop requirements


"""

import os
import sys
import time
import weakref
import json
import concurrent.futures
import traceback
import zmq


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
    def __init__(self, socket, call_id):
        concurrent.futures.Future.__init__(self)
        self.socket = socket
        self.call_id = call_id
    
    def cancel(self):
        return False

    def result(self, timeout=None):
        self.socket.process_until_future(self, timeout=timeout)
        return concurrent.futures.Future.result(self)


class RPCClientSocket(object):
    """A single socket for connecting to multiple RPC servers.
    
    This class should only be used to create RPCClient instances using
    `get_client()`.
    """
    def __init__(self):
        self.socket = zmq.Context.instance().socket(zmq.ROUTER)
        self._name = ('%d-%d' % (os.getpid(), id(self))).encode()
        self.socket.setsockopt(zmq.IDENTITY, self._name)
        self.clients = {}
        self.next_call_id = 0
        self.futures = weakref.WeakValueDictionary()
        
    def connect(self, addr):
        """Conncet the socket to an RPCServer address.
        
        May connect to multiple servers.
        """
        self.socket.connect(addr)
    
    def send(self, name, action, *args, **kwds):
        """Send a request to the remote process.
        
        Parameters
        ----------
        name : bytes
            The remote process's identifier string
        action : str
            The action to invoke on the remote process. For now, the only
            supported action is 'call'.
        """
        call_id = self.next_call_id
        self.next_call_id += 1
        cmd = {'action': action, 'call_id': call_id,
               'args': args, 'kwds': kwds}
        cmd = json.dumps(cmd).encode()
        #print("SEND:", name, cmd)
        self.socket.send_multipart([name, cmd])
        fut = Future(self, call_id)
        self.futures[call_id] = fut
        return fut

    def process(self):
        """Process all available incoming messages.
        """
        while True:
            try:
                name = self.socket.recv(zmq.NOBLOCK)
                msg = self.socket.recv_json()
                self._process_msg(name, msg)
            except zmq.error.Again:
                break  # no messages left

    def process_until_future(self, future, timeout=None):
        """Process all incoming messages until receiving a result for *future*.
        """
        while not future.done():
            # wait patiently with blocking calls.
            # TODO: implement timeout
            name = self.socket.recv()
            msg = self.socket.recv_json()
            self._process_msg(name, msg)

    def _process_msg(self, name, msg):
        """Handle one message received from the remote process.
        
        This takes care of assigning return values or exceptions to existing
        Future instances.
        """
        if msg['action'] == 'return':
            call_id = msg['call_id']
            if call_id not in self.futures:
                return
            fut = self.futures[call_id]
            if msg['error'] is not None:
                exc = RemoteCallException(*msg['error'])
                #print("GOT EXC:", exc)
                fut.set_exception(exc)
            else:
                fut.set_result(msg['rval'])
    

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
    socket : None or RPCClientSocket
        Optional RPCClientSocket object. Used to allow multiple RPCClients to
        share a single zmq socket.
    """
    def __init__(self, name, addr, socket=None):
        if socket is None:
            socket = RPCClientSocket()
        socket.connect(addr)
        self._name = name.encode()
        self._socket = socket
        self._methods = {}
        
    def __getattr__(self, name):
        return self._methods.setdefault(name, RPCMethod(self, name))
    
    def _call_method(self, method_name, *args, **kwds):
        return self._socket.send(self._name, 'call', method_name, *args, **kwds)

    
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


class RPCServer(object):
    """An RPC server abstract class.
    
    Subclasses must define any extra methods that may be called by the client.
    
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
        self._closed = False
        #print("START SERVER:", self._name)

    def _process_one(self):
        """Read one message from the remote client and invoke the requested
        action.
        
        This method sends back to the client either the return value or an
        error message.
        """
        name = self._socket.recv()
        msg = self._socket.recv_json()
        if msg['action'] == 'call':
            method, args = msg['args'][0], msg['args'][1:]
            kwds = msg['kwds']
            ret = kwds.pop('_return', True)
            try:
                call_id = msg['call_id']
                fn = getattr(self, method)
                if len(kwds) == 0:
                    # need to do this because some functions do not allow
                    # keyword arguments.
                    rval = fn(*args)
                else:
                    rval = fn(*args, **kwds)
                if ret:
                    self._send_result(name, call_id, rval=rval)
            except:
                exc = sys.exc_info()
                exc_str = traceback.format_exception(*exc)
                if ret:
                    self._send_result(name, call_id, error=(exc[0].__name__, exc_str))
        
    def _send_result(self, name, call_id, rval=None, error=None):
        #print("RESULT:", name, call_id, rval, error)
        result = {'action': 'return', 'call_id': call_id,
                  'rval': rval, 'error': error}
        self._socket.send_multipart([name, json.dumps(result).encode()])

    def close(self):
        """Close this RPC server.
        """
        self._closed = True
        self.socket.close()

    def running(self):
        """Boolean indicating whether the server is still running.
        """
        return not self._closed
    
    def run_forever(self):
        while self.running():
            self._process_one()
