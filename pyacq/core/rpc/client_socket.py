import os
import time
import weakref
import concurrent.futures
from logging import info
import zmq

from .serializer import serializer


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
        self._name = ('%d-%x' % (os.getpid(), id(self))).encode()
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
        cmd = serializer.dumps(cmd)
        info("RPC send req: %s => %s, %s", self.socket.getsockopt(zmq.IDENTITY), name, cmd)
        self.socket.send_multipart([name, cmd])
        fut = Future(self, call_id)
        self.futures[call_id] = fut
        return fut

    def process(self):
        """Process all available incoming messages.
        
        Return immediately if no messages are available.
        """
        while True:
            try:
                name = self.socket.recv(zmq.NOBLOCK)
                msg = self.socket.recv()
                msg = serializer.loads(msg)
                self._process_msg(name, msg)
            except zmq.error.Again:
                break  # no messages left

    def process_until_future(self, future, timeout=None):
        """Process all incoming messages until receiving a result for *future*.
        
        If the future result is not raised before the timeout, then raise
        TimeoutError.
        """
        start = time.perf_counter()
        while not future.done():
            # wait patiently with blocking calls.
            if timeout is None:
                itimeout = -1
            else:
                dt = time.perf_counter() - start
                itimeout = int((timeout - dt) * 1000)
                if itimeout < 0:
                    raise TimeoutError("Timeout waiting for Future result.")
            try:
                self.socket.setsockopt(zmq.RCVTIMEO, itimeout)
                name, msg = self.socket.recv_multipart()
                msg = serializer.loads(msg)
            except zmq.error.Again:
                raise TimeoutError("Timeout waiting for Future result.")
            
            self._process_msg(name, msg)

    def _process_msg(self, name, msg):
        """Handle one message received from the remote process.
        
        This takes care of assigning return values or exceptions to existing
        Future instances.
        """
        info("RPC recv res: %s %s", name, msg)
        if msg['action'] == 'return':
            call_id = msg['call_id']
            if call_id not in self.futures:
                return
            fut = self.futures[call_id]
            if msg['error'] is not None:
                exc = RemoteCallException(*msg['error'])
                fut.set_exception(exc)
            else:
                fut.set_result(msg['rval'])
    
    def close(self):
        self.socket.close()

    def __del__(self):
        self.close()
