import threading, atexit, time
import logging
from pyacq.core.rpc import RPCClient, RemoteCallException, RPCServer, ObjectProxy
import zmq.utils.monitor
import numpy as np


def test_rpc():
    previous_level = logging.getLogger().level
    logging.getLogger().level = logging.INFO
    
    class TestClass(object):
        count = 0
        def __init__(self):
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
    
    server = RPCServer(name='some_server', addr='tcp://*:*')
    server['test_class'] = TestClass
    server['my_object'] = TestClass()
    serve_thread = threading.Thread(target=server.run_forever, daemon=True)
    serve_thread.start()
    
    client = RPCClient.get_client(server.address)
    
    # test clients are cached
    assert client == RPCClient.get_client(server.address)
    try:
        # can't manually create client for the same address
        RPCClient(server.address)
        assert False, "Should have raised KeyError."
    except KeyError:
        pass
    
    # get proxy to TestClass instance
    obj = client['my_object']
    assert isinstance(obj, ObjectProxy)
    
    # test call / sync return
    add = obj.add
    assert isinstance(add, ObjectProxy)
    assert add(7, 5) == 12
    
    # NOTE: msgpack converts list to tuple. 
    # See: https://github.com/msgpack/msgpack-python/issues/98
    assert obj.get_list() == (0, 'x', 7)

    # test async return
    fut = obj.sleep(0.1, _sync='async')
    assert not fut.done()
    assert fut.result() is None

    # test no return
    assert obj.add(1, 2, _sync='off') is None

    # test return by proxy
    list_prox = obj.get_list(_return_type='proxy')
    assert isinstance(list_prox, ObjectProxy)
    assert list_prox._type_str == "<class 'list'>"
    assert len(list_prox) == 3
    assert list_prox[2] == 7

    # Test remote exception raising
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

    # test deferred getattr
    arr = obj.array(_return_type='proxy')
    dt1 = arr.dtype.name
    assert isinstance(dt1, ObjectProxy)
    assert dt1._attributes == ()
    assert dt1._get_value() == 'int64'
    arr._set_proxy_options(defer_getattr=True)
    dt2 = arr.dtype.name
    assert isinstance(dt2, ObjectProxy)
    assert dt2._obj_id == arr._obj_id
    assert dt2._attributes == ('dtype', 'name')
    dt3 = dt2._undefer()
    assert dt3._attributes == ()
    assert dt3._get_value() == 'int64'

    # test remote object creation / deletion
    class_proxy = client['test_class']
    obj2 = class_proxy()
    assert class_proxy.count == 2
    assert obj2.add(3, 4) == 7
    del obj2
    # reference management is temporarily disabled.
    #assert class_proxy.count == 1

    # test timeouts
    try:
        obj.sleep(0.2, _timeout=0.01)
    except TimeoutError:
        pass
    else:
        raise AssertionError('should have raised TimeoutError')

    # test result order
    a = obj.add(1, 2, _sync='async')
    b = obj.add(3, 4, _sync='async')
    assert b.result() == 7
    assert a.result() == 3



    # test multiple clients per server
    #  disabled for now--need to put this in another thread because we don't
    #  allow multiple clients per thread
    #client2 = RPCClient('tcp://localhost:5152')
    
    #obj2 = client2['my_object']
    #a = obj2.add(1, 2, _sync='async')
    #b = obj.add(3, 4, _sync='async')
    #c = obj2.add(5, 6, _sync='async')
    #assert b.result() == 7
    #assert a.result() == 3
    #assert c.result() == 11
    
    
    client.close_server()
    client.close()
    serve_thread.join()
    
    logging.getLogger().level = previous_level



if __name__ == '__main__':
    test_rpc()
    test_serializer()
