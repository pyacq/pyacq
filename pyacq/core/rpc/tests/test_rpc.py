import threading, atexit, time
import logging
from pyacq.core.rpc import RPCClient, RemoteCallException, RPCServer
from pyacq.core.rpc.serializer import JsonSerializer, MsgpackSerializer, HAVE_MSGPACK
import zmq.utils.monitor
import numpy as np
import datetime




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
            return np.arange(20)
   
        def sleep(self, t):
            time.sleep(t)
    
    server = RPCServer(name='some_server', addr='tcp://*:*')
    server['test_class'] = TestClass
    server['my_object'] = TestClass()
    serve_thread = threading.Thread(target=server.run_forever, daemon=True)
    serve_thread.start()
    
    client = RPCClient('some_server', server.address)
    obj = client['my_object']  # get proxy to TestClass instance
    
    # test proxies are cached
    assert obj is client['my_object']

    # test call / sync return
    assert obj.add(7, 5) == 12

    # test async return
    fut = obj.sleep(0.1, _sync=False)
    assert not fut.done()
    assert fut.result() is None

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
    except RemoteCallException as err:
        if err.type_str != 'AttributeError':
            raise
    else:
        raise AssertionError('should have raised AttributeError')

    # test remote object creation / deletion
    class_proxy = client['test_class']
    obj2 = class_proxy()
    assert class_proxy.count == 2
    assert obj2.add(3, 4) == 7
    del obj2
    assert class_proxy.count == 1

    # test timeouts
    try:
        obj.sleep(0.2, _timeout=0.01)
    except TimeoutError:
        pass
    else:
        raise AssertionError('should have raised TimeoutError')

    # test result order
    a = obj.add(1, 2, _sync=False)
    b = obj.add(3, 4, _sync=False)
    assert b.result() == 7
    assert a.result() == 3

    # test multiple clients per server
    client2 = RPCClient('some_server', 'tcp://localhost:5152')
    
    obj2 = client2['my_object']
    a = obj2.add(1, 2, _sync=False)
    b = obj.add(3, 4, _sync=False)
    c = obj2.add(5, 6, _sync=False)
    assert b.result() == 7
    assert a.result() == 3
    assert c.result() == 11

    # test multiple clients sharing one socket
    # skipping this test--clients currently do not support socket sharing
    #server2 = Server1(name='some_server2', addr='tcp://*:5153')
    #serve_thread2 = threading.Thread(target=server2.run_forever, daemon=True)
    #serve_thread2.start()
    
    #client3 = RPCClient('some_server2', 'tcp://localhost:5153',
                        #rpc_socket=client2._rpc_socket)
    
    #a = client2.add(1, 2, _sync=False)
    #b = client3.add(3, 4, _sync=False)
    #assert b.result() == 7
    #assert a.result() == 3
    
    #client3.close()
    #serve_thread2.join()
    
    client.close()
    serve_thread.join()
    
    logging.getLogger().level=previous_level


def test_serializer():
    d = dict(a=1, b=1., c='abc', 
                d=b'abc',
                e=np.arange(8).reshape(2, 4).astype('float64'),
                f=datetime.datetime(2015, 1, 1, 12, 00, 00),
                g=datetime.date(2015, 1, 1),
                )
    
    serializers = [JsonSerializer()]
    if HAVE_MSGPACK:
        serializers.append(MsgpackSerializer())
    
    for serializer in serializers:
        s = serializer.dumps(d)
        d2 = serializer.loads(s)
        for k in d:
            assert type(d[k]) is type(d2[k])
    

if __name__ == '__main__':
    test_rpc()
    test_serializer()
