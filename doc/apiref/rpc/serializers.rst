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

It is possible to add support for new serializers by modifying
``pyacq.core.rpc.serializer.all_serializers``.

Serializable data types are:

* Basic Python types: int, float, string, dict, list, date, datetime
* Binary types: bytes, numpy.ndarray  (efficient with msgpack)

Note that both serializers convert tuples into lists.




.. autoclass:: Serializer
   :members:


