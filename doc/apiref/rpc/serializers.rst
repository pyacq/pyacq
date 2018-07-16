.. currentmodule:: pyacq.core.rpc.serializer

.. _apiref_rpc_serializers:

Serializers
===========

Serializers provide a mechanism for some data types to be copied from one process
to another by converting Python objects into byte strings and vice-versa.
Currently, two serializer classes are supported:
    
* **msgpack** provides efficient serialization for all supported types, including
  large binary data.
* **json** is somewhat less efficient in encoding large binary data, but is more
  universally supported across platforms where msgpack may be unavailable.

The basic types supported by both serializers are ``int``, ``float``, ``str``,
``dict``, and ``list``. Further data types are serialized by first converting
to a dict containing the key ``___type_name___`` in order to distinguish it 
from normal dicts (see :func:`Serializer.encode` and :func:`Serializer.decode`)::
    
    datetime = {
        '___type_name___': 'datetime',
        'data': obj.strftime('%Y-%m-%dT%H:%M:%S.%f')
    }
    
    date = {
        '___type_name___': 'date',
        'data': obj.strftime('%Y-%m-%d')
    }
    
    nonetype = {
        '___type_name___': 'none'
    }
    
    objectproxy = {
        '___type_name___': 'proxy',
        'rpc_addr': obj._rpc_addr, 
        'obj_id': obj._obj_id,
        'ref_id': obj._ref_id,
        'type_str': obj._type_str,
        'attributes': obj._attributes,
    }

Types containing byte strings are handled differently between msgpack and json.
In msgpack, byte strings are natively supported::

    np.ndarray = {
        '___type_name___': 'ndarray',
        'data': array.tostring(),
        'dtype': str(array.dtype),
        'shape': array.shape
    }
    
    # no need to convert; msgpack already handles this type
    bytes = bytes_obj
    
However json does not support byte strings, so in this case the strings must
be base-64 encoded before being serialized::
    
    ndarray = {
        '___type_name___': 'ndarray',
        'data': base64.b64encode(array.data).decode(),
        'dtype': str(array.dtype),
        'shape': array.shape
    }
    
    bytes = {
        '__type_name__': 'bytes',
        'data': base64.b64encode(bytes_obj).decode()
    }


Note that both serializers convert tuples into lists automatically. This is
undesirable, but is currently not configurable in a consistent way across both
serializers.

It is possible to add support for new serializers by creating a subclass of
:class:`Serializer` and modifying ``pyacq.core.rpc.serializer.all_serializers``.





.. autoclass:: Serializer
   :members:


