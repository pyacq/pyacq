.. currentmodule:: pyacq.core.rpc

.. _apiref_rpc_proxy:

ObjectProxy and Future
======================

After initial setup, these classes are the main API through which a remote
process is controlled.

.. autoclass::  pyacq.core.rpc.ObjectProxy
   :members: _set_proxy_options, _get_value, __getattr__, __setattr__, __call__, __getitem__, __setitem__, _delete 

.. autoclass:: pyacq.core.rpc.Future
   :members:
