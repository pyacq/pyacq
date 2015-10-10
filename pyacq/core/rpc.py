import os
import sys
import time
import weakref
import concurrent.futures
import traceback
import zmq
import atexit
from logging import info
import numpy as np
import datetime
import base64

import json
try:
    import msgpack
    HAVE_MSGPACK = True
except ImportError:
    HAVE_MSGPACK = False


# Any type that is not supported by json/msgpack must be encoded as a dict.
# To distinguish these from plain dicts, we include a unique key in them:
encode_key = '___type_name___'


def enchance_encode(obj):
    """
    JSon/msgpack encoder that support date, datetime and numpy array, and bytes.
    Mix of various stackoverflow solution.
    """
    
    if isinstance(obj, np.ndarray):
        if not obj.flags['C_CONTIGUOUS']:
            obj = np.ascontiguousarray(obj)
        assert(obj.flags['C_CONTIGUOUS'])
        return {encode_key: 'ndarray',
                'data': base64.b64encode(obj.data).decode(),
                'dtype': str(obj.dtype),
                'shape': obj.shape}
    elif isinstance(obj, datetime.datetime):
        return {encode_key: 'datetime',
                'data': obj.strftime('%Y-%m-%dT%H:%M:%S.%f')}
    elif isinstance(obj, datetime.date):
        return {encode_key: 'date',
                'data': obj.strftime('%Y-%m-%d')}
    elif isinstance(obj, bytes):
        return {encode_key: 'bytes',
                'data': base64.b64encode(obj).decode()}
    else:
        return obj


def enchanced_decode(dct):
    """
    JSon/msgpack decoder that support date, datetime and numpy array, and bytes.
    Mix of various stackoverflow solution.
    """
    if isinstance(dct, dict):
        type_name = dct.get(encode_key, None)
        if type_name is None:
            return dct
        if type_name == 'ndarray':
            data = base64.b64decode(dct['data'])
            return np.frombuffer(data, dct['dtype']).reshape(dct['shape'])
        elif type_name == 'datetime':
            return datetime.datetime.strptime(dct['data'], '%Y-%m-%dT%H:%M:%S.%f')
        elif type_name == 'date':
            return datetime.datetime.strptime(dct['data'], '%Y-%m-%d').date()
        elif type_name == 'bytes':
            return base64.b64decode(dct['data'])
    return dct


class EnhancedJSONEncoder(json.JSONEncoder):
    def default(self, obj):
        obj2 = enchance_encode(obj)
        if obj is obj2:
            return json.JSONEncoder.default(self, obj)
        else:
            return obj2


class JsonSerializer:
    def dumps(self, obj):
        return json.dumps(obj, cls=EnhancedJSONEncoder).encode()
    
    def loads(self, msg):
        return json.loads(msg.decode(), object_hook=enchanced_decode)


class MsgpackSerializer:
    def __init__(self):
        assert HAVE_MSGPACK
    
    def dumps(self, obj):
        return msgpack.dumps(obj, use_bin_type=True, default=enchance_encode)

    def loads(self, msg):
        return msgpack.loads(msg, encoding='utf8', object_hook=enchanced_decode)

    
serializer = JsonSerializer()
# serializer = MsgpackSerializer()



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
        # atexit.register(self.close)
        
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
        self._addr = self._socket.getsockopt(zmq.LAST_ENDPOINT)
        self._closed = False
        info("RPC start server: %s@%s", self._name.decode(), self._addr.decode())
        # atexit.register(self.close)

    def __del__(self):
        self._socket.close()

    def _read_and_process_one(self):
        """Read one message from the remote client and invoke the requested
        action.
        
        This method sends back to the client either the return value or an
        error message.
        """
        
        name, msg = self._read_socket()
        self._process_one(name, msg)
        
    def _read_socket(self):
        """Read one message from the remote client
        """
        if not self.running:
            raise RuntimeError("RPC server socket is already closed.")
            
        name, msg = self._socket.recv_multipart()
        info("RPC recv req: %s %s", name, msg)
        return name, msg
        
    def _process_one(self, name, msg):
        """
        Invoke the requested action.
        """
        msg = serializer.loads(msg)
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
                    self._send_result(*self._format_result(name, call_id, rval=rval))
            except:
                exc_str = ["Error while processing request %s.%s(%s, %s)" % (str(self), method, args, kwds)]
                exc_str += traceback.format_stack()
                exc_str += [" < exception caught here >\n"]
                exc = sys.exc_info()
                exc_str += traceback.format_exception(*exc)
                if ret:
                    self._send_result(*self._format_result(name, call_id, error=(exc[0].__name__, exc_str)))
    
    def _format_result(self, name, call_id, rval=None, error=None):
        result = {'action': 'return', 'call_id': call_id,
                  'rval': rval, 'error': error}
        info("RPC send res: %s %s", name, result)
        return name, serializer.dumps(result)
    
    def _send_result(self, name, data):
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

    def ping(self):
        return 'pong'
