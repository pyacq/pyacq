import threading, atexit, time, logging
from pyacq.core.rpc import RPCClient, RemoteCallException, RPCServer, QtRPCServer, ObjectProxy, ProcessSpawner
from pyacq.core.rpc.log import RPCLogHandler, set_process_name, set_thread_name, start_log_server
import zmq.utils.monitor
import numpy as np
import pyqtgraph as pg
from pyqtgraph.Qt import QtCore, QtGui


# Set up nice logging for tests:
# remote processes forward logs to this process
logger = logging.getLogger()
#logger.level = logging.DEBUG
start_log_server(logger)
# local log messages are time-sorted and colored
handler = RPCLogHandler()
logger.addHandler(handler)
# messages originating locally can be easily identified
set_process_name('main_process')
set_thread_name('main_thread')


qapp = pg.mkQApp()


def test_rpc():
    previous_level = logger.level
    #logger.level = logging.DEBUG
    
    class TestClass(object):
        count = 0
        def __init__(self, name):
            self.name = name
            TestClass.count += 1

        def __del__(self):
            TestClass.count -= 1
        
        def add(self, x, y):
            return x + y
        
        def array(self):
            return np.arange(20).astype('int64')
   
        def sleep(self, t):
            time.sleep(t)
            
        def get_list(self):
            return [0, 'x', 7]
        
        def test(self, obj):
            return self.name, obj.name, obj.add(5, 7), obj.array(), obj.get_list()

        def types(self):
            return {'int': 7, 'float': 0.5, 'str': 'xxx', 'bytes': bytes('xxx', 'utf8'),
                    'ndarray': np.arange(10), 'dict': {}, 'list': [],
                    'ObjectProxy': self}
    
        def type(self, x):
            return type(x).__name__
    
    
    server1 = RPCServer()
    server1['test_class'] = TestClass
    server1['my_object'] = TestClass('obj1')
    serve_thread = threading.Thread(target=server1.run_forever, daemon=True)
    serve_thread.start()
    
    client = RPCClient.get_client(server1.address)
    
    # test clients are cached
    assert client == RPCClient.get_client(server1.address)
    try:
        # can't manually create client for the same address
        RPCClient(server1.address)
        assert False, "Should have raised KeyError."
    except KeyError:
        pass
    
    # get proxy to TestClass instance
    obj = client['my_object']
    assert isinstance(obj, ObjectProxy)
    
    logger.info("-- Test call with sync return --")
    add = obj.add
    assert isinstance(add, ObjectProxy)
    assert add(7, 5) == 12

    # test return types
    for k, v in obj.types().items():
        assert type(v).__name__ == k
        if k != 'ObjectProxy':
            assert obj.type(v) == k

    # NOTE: msgpack converts list to tuple. 
    # See: https://github.com/msgpack/msgpack-python/issues/98
    assert obj.get_list() == [0, 'x', 7]

    logger.info("-- Test async return --")
    fut = obj.sleep(0.1, _sync='async')
    assert not fut.done()
    assert fut.result() is None

    logger.info("-- Test no return --")
    assert obj.add(1, 2, _sync='off') is None

    logger.info("-- Test return by proxy --")
    list_prox = obj.get_list(_return_type='proxy')
    assert isinstance(list_prox, ObjectProxy)
    assert list_prox._type_str == "<class 'list'>"
    assert len(list_prox) == 3
    assert list_prox[2] == 7

    logger.info("-- Test proxy access to server --")
    srv = client['self']
    assert srv.address == server1.address


    logger.info("-- Test remote exception raising --")
    try:
        obj.add(7, 'x')
    except RemoteCallException as err:
        if err.type_str != 'TypeError':
            raise
    else:
        raise AssertionError('should have raised TypeError')

    try:
        client.asdffhgk
        raise AssertionError('should have raised AttributeError')
    except AttributeError:
        pass

    logger.info("-- Test deferred getattr --")
    arr = obj.array(_return_type='proxy')
    dt1 = arr.dtype.name._get_value()
    assert isinstance(dt1, str)
    arr._set_proxy_options(defer_getattr=True)
    dt2 = arr.dtype.name
    assert isinstance(dt2, ObjectProxy)
    assert dt2._obj_id == arr._obj_id
    assert dt2._attributes == ('dtype', 'name')
    dt3 = dt2._undefer()
    assert dt3 == dt2

    logger.info("-- Test remote object creation / deletion --")
    class_proxy = client['test_class']
    obj2 = class_proxy('obj2')
    assert class_proxy.count == 2
    assert obj2.add(3, 4) == 7
    
    obj2._delete()
    handler.flush_records()  # log records might have refs to the object
    assert class_proxy.count._get_value() == 1
    try:
        obj2.array()
        assert False, "Should have raised RemoteCallException"
    except RemoteCallException:
        pass

    logger.info("-- Test proxy auto-delete --")
    obj2 = class_proxy('obj2')
    obj2._set_proxy_options(auto_delete=True)
    assert class_proxy.count == 2
    
    del obj2
    handler.flush_records()  # log records might have refs to the object
    assert class_proxy.count._get_value() == 1


    logger.info("-- Test timeouts --")
    try:
        obj.sleep(0.2, _timeout=0.01)
    except TimeoutError:
        pass
    else:
        raise AssertionError('should have raised TimeoutError')
    obj.sleep(0.2, _timeout=0.5)

    logger.info("-- Test result order --")
    a = obj.add(1, 2, _sync='async')
    b = obj.add(3, 4, _sync='async')
    assert b.result() == 7
    assert a.result() == 3

    
    logger.info("-- Test transfer --")
    arr = np.ones(10, dtype='float32')
    arr_prox = client.transfer(arr)
    assert arr_prox.dtype.name == 'float32'
    print(arr_prox, arr_prox.shape)
    assert arr_prox.shape._get_value() == [10]


    logger.info("-- Test import --")
    import os.path as osp
    rosp = client._import('os.path')
    assert osp.abspath(osp.dirname(__file__)) == rosp.abspath(rosp.dirname(__file__))


    logger.info("-- Test proxy sharing between servers --")
    obj._set_proxy_options(defer_getattr=True)
    r1 = obj.test(obj)
    server2 = RPCServer()
    server2['test_class'] = TestClass
    serve_thread2 = threading.Thread(target=server2.run_forever, daemon=True)
    serve_thread2.start()
    
    client2 = RPCClient(server2.address)
    client2.default_proxy_options['defer_getattr'] = True
    obj3 = client2['test_class']('obj3')
    # send proxy from server1 to server2
    r2 = obj3.test(obj)
    # check that we have a new client between the two servers
    assert (serve_thread2.ident, server1.address) in RPCClient.clients_by_thread 
    # check all communication worked correctly
    assert r1[0] == 'obj1'
    assert r2[0] == 'obj3'
    assert r1[1] == r2[1] == 'obj1'
    assert r1[2] == r2[2] == 12
    assert np.all(r1[3] == r2[3])
    assert r1[4] == r2[4]
    
    logger.info("-- Test publishing objects --")
    arr = np.arange(5, 10)
    client['arr'] = arr  # publish to server1
    s2rpc = client2._import('pyacq.core.rpc')
    s2cli = s2rpc.RPCClient.get_client(client.address)  # server2's client for server1
    assert np.all(s2cli['arr'] == arr)  # retrieve via server2

    logger.info("-- Test JSON client --")
    # Start a JSON client in a remote process
    cli_proc = ProcessSpawner()
    cli = cli_proc.client._import('pyacq.core.rpc').RPCClient(server2.address, serializer='json')
    # Check everything is ok..
    assert cli.serializer.type._get_value() == 'json'
    assert cli['test_class']('json-tester').add(3, 4) == 7
    cli_proc.kill()

    
    logger.info("-- Setup reentrant communication test.. --")
    class PingPong(object):
        def set_other(self, o):
            self.other = o
        def pingpong(self, depth=0):
            if depth > 6:
                return "reentrant!"
            return self.other.pingpong(depth+1)

    server1['pp1'] = PingPong()
    server2['pp2'] = PingPong()
    pp1 = client['pp1']
    pp2 = client2['pp2']
    pp1.set_other(pp2)
    pp2.set_other(pp1)
    
    logger.info("-- Test reentrant communication --")
    assert pp1.pingpong() == 'reentrant!'

    
    logger.info("-- Shut down servers --")
    client2.close_server()
    serve_thread2.join()
    
    
    client.close_server()
    client.close()
    serve_thread.join()
    
    logger.level = previous_level


def test_qt_rpc():
    previous_level = logger.level
    #logger.level = logging.DEBUG
    
    server = QtRPCServer(quit_on_close=False)
    server.run_forever()
    
    # Start a thread that will remotely request a widget to be created in the 
    # GUI thread.
    class TestThread(threading.Thread):
        def __init__(self, addr):
            threading.Thread.__init__(self, daemon=True)
            self.addr = addr
            self.done = False
            self.lock = threading.Lock()
        
        def run(self):
            client = RPCClient(self.addr)
            qt = client._import('pyqtgraph.Qt')
            # widget creation happens in main GUI thread; we are working with
            # proxies from here.
            self.l = qt.QtGui.QLabel('remote-controlled label')
            self.l.show()
            time.sleep(0.3)
            self.l.hide()
            with self.lock:
                self.done = True
    
    thread = TestThread(server.address)
    thread.start()
    
    start = time.time()
    while True:
        with thread.lock:
            if thread.done:
                break
        assert time.time() < start + 5.0, "Thread did not finish within 5 sec."
        time.sleep(0.01)
        qapp.processEvents()

    assert 'QLabel' in thread.l._type_str
    server.close()

    logger.level = previous_level

def test_disconnect():
    #logger.level = logging.DEBUG
    
    # Clients receive notification when server disconnects gracefully
    server_proc = ProcessSpawner()
    
    client_proc = ProcessSpawner()
    cli = client_proc.client._import('pyacq.core.rpc').RPCClient(server_proc.client.address)
    cli.close_server()

    assert cli.disconnected() is True
    
    assert server_proc.client.disconnected() is True
    try:
        print(server_proc.client.ping())
        assert False, "Expected RuntimeError"
    except RuntimeError:
        pass
    

    # Clients receive closure messages even if the server exits without closing
    server_proc = ProcessSpawner()
    server_proc.client['self']._closed = 'sabotage!'
    time.sleep(0.1)
    assert server_proc.client.disconnected() is True
    
    
    # Clients gracefully handle sudden death of server (with timeout)
    server_proc = ProcessSpawner()
    server_proc.kill()
    
    try:
        server_proc.client.ping(timeout=1)
        assert False, "Expected TimeoutError"
    except TimeoutError:
        pass


    # server doesn't hang up if clients are not available to receive disconnect
    # message
    server_proc = ProcessSpawner()
    for i in range(4):
        # create a bunch of dead clients
        cp = ProcessSpawner()
        cli = cp.client._import('pyacq.core.rpc').RPCClient(server_proc.client.address)
        cp.kill()
    
    start = time.time()
    server_proc.client.close_server()
    assert time.time() - start < 1.0
    assert server_proc.client.disconnected() == True



if __name__ == '__main__':
    test_rpc()
    test_serializer()
