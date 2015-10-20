import numpy as np
import datetime
import base64
import json
try:
    import msgpack
    HAVE_MSGPACK = True
except ImportError:
    HAVE_MSGPACK = False

from .proxy import ObjectProxy


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
    """Class for serializing objects using msgpack.
    
    Supports ndarray, date, datetime, and bytes for transfer in addition to the
    standard list supported by msgpack. All other types are converted to an
    object proxy that can be used to access methods / attributes of the object
    remotely (this requires that the object be owned by an RPC server).
    """
    def __init__(self, server=None):
        self.server = server
        assert HAVE_MSGPACK
    
    def dumps(self, obj):
        """Convert obj to msgpack string.
        """
        return msgpack.dumps(obj, use_bin_type=True, default=self.encode)

    def loads(self, msg):
        """Convert from msgpack string to python object.
        
        Proxies that reference objects owned by the server are converted back
        into the local object. All other proxies are left as-is.
        """
        return msgpack.loads(msg, encoding='utf8', object_hook=self.decode)

    def encode(self, obj):
        if isinstance(obj, (str, bytes, int, float, list, tuple, dict)):
            return obj
        elif isinstance(obj, np.ndarray):
            if not obj.flags['C_CONTIGUOUS']:
                obj = np.ascontiguousarray(obj)
            assert(obj.flags['C_CONTIGUOUS'])
            return {encode_key: 'ndarray',
                    'data': obj.tostring(),
                    'dtype': str(obj.dtype),
                    'shape': obj.shape}
        elif isinstance(obj, datetime.datetime):
            return {encode_key: 'datetime',
                    'data': obj.strftime('%Y-%m-%dT%H:%M:%S.%f')}
        elif isinstance(obj, datetime.date):
            return {encode_key: 'date',
                    'data': obj.strftime('%Y-%m-%d')}
        else:
            # All unrecognized types must be converted to proxy.
            if self.server is None:
                raise TypeError("Cannot serialize type %s without proxy server." % type(obj))
            if not isinstance(obj, ObjectProxy):
                obj = self.server.get_proxy(obj)
            ser = {encode_key: 'proxy'}
            ser.update(obj.save())
            return ser

    def decode(self, dct):
        if isinstance(dct, dict):
            type_name = dct.pop(encode_key, None)
            if type_name is None:
                return dct
            if type_name == 'ndarray':
                return np.fromstring(data, dtype=dct['dtype']).reshape(dct['shape'])
            elif type_name == 'datetime':
                return datetime.datetime.strptime(dct['data'], '%Y-%m-%dT%H:%M:%S.%f')
            elif type_name == 'date':
                return datetime.datetime.strptime(dct['data'], '%Y-%m-%d').date()
            elif type_name == 'proxy':
                proxy = ObjectProxy(**dct)
                return self.server.lookup_proxy(proxy)
        return dct
    
#serializer = JsonSerializer()
# serializer = MsgpackSerializer()
