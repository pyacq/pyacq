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
