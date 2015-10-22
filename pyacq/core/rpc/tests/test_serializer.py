import numpy as np
import datetime

from pyacq.core.rpc.serializer import JsonSerializer, MsgpackSerializer, HAVE_MSGPACK


def test_serializer():
    d = dict(a=1, b=1., c='abc', 
                d=b'abc',
                e=np.arange(8).reshape(2, 4).astype('float64'),
                f=datetime.datetime(2015, 1, 1, 12, 00, 00),
                g=datetime.date(2015, 1, 1),
                h=(1,2),
                #i=[1,2],  # msgpack only returns tuples, not lists (because we have use_list=False).
                           # see: https://github.com/msgpack/msgpack-python/issues/98
                )
    
    #serializers = [JsonSerializer()]
    #if HAVE_MSGPACK:
        #serializers.append(MsgpackSerializer())
    serializers = [MsgpackSerializer()]
    
    for serializer in serializers:
        s = serializer.dumps(d)
        d2 = serializer.loads(s)
        for k in d:
            assert type(d[k]) is type(d2[k])
    
