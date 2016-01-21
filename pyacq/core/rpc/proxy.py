# -*- coding: utf-8 -*-
# Copyright (c) 2016, French National Center for Scientific Research (CNRS)
# Distributed under the (new) BSD License. See LICENSE for more info.

import os
import weakref


class ObjectProxy(object):
    """
    Proxy to an object stored by a remote :class:`RPCServer`.
    
    A proxy behaves in most ways like the object that it wraps--you can request
    the same attributes, call methods, etc. There are a few important
    differences:
    
    * A proxy can be on a different thread, process, or machine than its object,
      so long as the object's thread has an RPCServer and the proxy's thread has
      an associated RPCClient.
    * Attribute lookups and method calls can be slower because the request and
      response must traverse a socket. These can also be performed asynchronously
      to avoid blocking the client thread.
    * Function argument and return types must be serializable or proxyable.
      Most basic types can be serialized, including numpy arrays. All other
      objects are automatically proxied, but there are some cases when this will
      not work well.
    * :func:`__repr__` and :func:`__str__` are overridden on proxies to allow
      safe debugging.
    * :func:`__hash__` is overridden to ensure that remote hash values are not
      used locally.

    
    For the most part, object proxies can be used exactly as if they are
    local objects::
    
        client = RPCClient(address)  # connect to RPCServer
        rsys = client._import('sys') # returns proxy to sys module on remote process
        rsys.stdout.write            # proxy to remote sys.stdout.write
        rsys.stdout.write('hello')   # calls sys.stdout.write('hello') on remote machine
                                     # and returns the result (None)
    
    When calling a proxy to a remote function, the call can be made synchronous
    (caller is blocked until result can be returned), asynchronous (Future is
    returned immediately and result can be accessed later), or return can be
    disabled entirely::
    
        ros = proc._import('os')
        
        # synchronous call; caller blocks until result is returned
        pid = ros.getpid()
        
        # asynchronous call
        request = ros.getpid(_sync='async')
        while not request.hasResult():
            time.sleep(0.01)
        pid = request.result()
        
        # disable return when we know it isn't needed.
        rsys.stdout.write('hello', _sync='off')
    
    Additionally, values returned from a remote function call are automatically
    returned either by value (must be picklable) or by proxy. 
    This behavior can be forced::
    
        rnp = proc._import('numpy')
        arrProxy = rnp.array([1,2,3,4], _return_type='proxy')
        arrValue = rnp.array([1,2,3,4], _return_type='value')
    
    The default sync and return_type behaviors (as well as others) can be set 
    for each proxy individually using ObjectProxy._set_proxy_options() or globally using 
    proc.set_proxy_options(). 
    
    It is also possible to send arguments by proxy if an RPCServer is running
    in the caller's thread (this can be used, for example, to connect Qt
    signals across network connections)::
    
        def callback():
            print("called back.")
            
        # Remote process can invoke our callback function as long as there is 
        # a server running here to process the request.
        remote_object.set_callback(proxy(callback))
    
    """
    
    def __init__(self, rpc_addr, obj_id, ref_id, type_str='', attributes=(), **kwds):
        object.__init__(self)
        ## can't set attributes directly because setattr is overridden.
        self.__dict__.update(dict(
            _rpc_addr=rpc_addr,
            _obj_id=obj_id,
            _ref_id=ref_id,
            _type_str=type_str,
            _attributes=attributes,
            _parent_proxy=None,
            _hash=hash((rpc_addr, obj_id, attributes)),
            # identify local client/server instances this proxy belongs to
            _client_=None,
            _server_=None,
        ))
        
        ## attributes that affect the behavior of the proxy. 
        self.__dict__['_proxy_options'] = {
            'sync': 'sync',      ## 'sync', 'async', 'off'
            'timeout': 10,            ## float
            'return_type': 'auto',    ## 'proxy', 'value', 'auto'
            #'auto_proxy_args': False, ## bool
            'defer_getattr': True,   ## True, False
            'no_proxy_types': [type(None), str, int, float, tuple, list, dict, ObjectProxy],
            'auto_delete': False,
        }
        
        self._set_proxy_options(**kwds)
    
    def _copy(self):
        # Return a copy of this proxy. 
        # This is used for transferring proxies across threads (because an
        # ObjectProxy should only be used in one thread.
        prox = ObjectProxy(self._rpc_addr, self._obj_id, self._ref_id, self._type_str, 
                           self._attributes, **self._proxy_options)
        if self._parent_proxy is not None:
            prox._parent_proxy = self._parent_proxy.copy()
        return prox

    def _client(self):
        if self._client_ is None:
            from .client import RPCClient
            self.__dict__['_client_'] = RPCClient.get_client(self._rpc_addr)
        return self._client_
        
    def _server(self):
        if self._server_ is None:
            from .server import RPCServer
            self.__dict__['_server_'] = RPCServer.get_server()
        return self._server_
    
    def _set_proxy_options(self, **kwds):
        """
        Change the behavior of this proxy. For all options, a value of None
        will cause the proxy to instead use the default behavior defined
        by its parent Process.
        
        Parameters
        ----------
        sync : 'sync', 'async', 'off', or None
            If 'async', then calling methods will return a :class:`Future` object
            that can be used to inquire later about the result of the 
            method call.
            If 'sync', then calling a method
            will block until the remote process has returned its result
            or the timeout has elapsed (in this case, a Request object
            is returned instead).
            If 'off', then the remote process is instructed *not* to 
            reply and the method call will return None immediately.
            This option can be overridden by supplying a ``_sync`` keyword
            argument when calling the method (see :func:`__call__`).
        return_type : 'auto', 'proxy', 'value', or None
            If 'proxy', then the value returned when calling a method
            will be a proxy to the object on the remote process.
            If 'value', then attempt to pickle the returned object and
            send it back.
            If 'auto', then the decision is made by consulting the
            'no_proxy_types' option.
            This option can be overridden by supplying a ``_return_type`` keyword
            argument when calling the method (see :func:`__call__`).
        auto_proxy : bool or None
            If True, arguments to __call__ are 
            automatically converted to proxy unless their type is 
            listed in no_proxy_types (see below). If False, arguments
            are left untouched. Use proxy(obj) to manually convert
            arguments before sending. 
        timeout : float or None
            Length of time to wait during synchronous 
            requests before returning a Request object instead.
            This option can be overridden by supplying a ``_timeout`` keyword
            argument when calling a method (see :func:`__call__`).
        defer_getattr : True, False, or None
            If False, all attribute requests will be sent to the remote 
            process immediately and will block until a response is
            received (or timeout has elapsed).
            If True, requesting an attribute from the proxy returns a
            new proxy immediately. The remote process is *not* contacted
            to make this request. This is faster, but it is possible to 
            request an attribute that does not exist on the proxied
            object. In this case, AttributeError will not be raised
            until an attempt is made to look up the attribute on the
            remote process.
        no_proxy_types : list
            List of object types that should *not* be proxied when
            sent to the remote process.
        auto_delete : bool
            If True, then the proxy will automatically call
            `self._delete()` when it is collected by Python.
        """
        for k in kwds:
            if k not in self._proxy_options:
                raise KeyError("Unrecognized proxy option '%s'" % k)
        self._proxy_options.update(kwds)

    def _save(self):
        """Convert this proxy to a serializable structure.
        """
        state = {
            'rpc_addr': self._rpc_addr, 
            'obj_id': self._obj_id,
            'ref_id': self._ref_id,
            'type_str': self._type_str,
            'attributes': self._attributes,
        }
        # TODO: opts DO need to be sent in some cases, like when sending
        # callbacks.
        #state.update(self._proxy_options)
        return state
        
    def _get_value(self):
        """
        Return the value of the proxied object.
        
        If the object is not serializable, then raise an exception.
        """
        if self._client() is None:
            return self._server().unwrap_proxy(self)
        else:
            return self._client().get_obj(self, return_type='value')
        
    def __repr__(self):
        orep = '.'.join((self._type_str,) + self._attributes)
        rep = '<ObjectProxy for %s[%d] %s >' % (self._rpc_addr.decode(), self._obj_id, orep)
        return rep

    def _undefer(self, sync='sync', return_type='auto', **kwds):
        """Process any deferred attribute lookups and return the result.
        """
        if len(self._attributes) == 0:
            return self
        # Transfer sends this object to the remote process and returns a new proxy.
        # In the process, this invokes any deferred attributes.
        return self._client().get_obj(self, sync=sync, return_type=return_type, **kwds)
        
    def _delete(self, sync='sync', **kwds):
        """Ask the RPC server to release the reference held by this proxy.
        
        Note: this does not guarantee the remote object will be deleted; only
        that its reference count will be reduced. Any copies of this proxy will
        no longer be usable.
        """
        self._client().delete(self, sync=sync, **kwds)
        
    def __del__(self):
        if self._proxy_options['auto_delete'] is True:
            self._delete()
        
    def __getattr__(self, attr):
        """
        Calls __getattr__ on the remote object and returns the attribute
        by value or by proxy depending on the options set (see
        ObjectProxy._set_proxy_options and RemoteEventHandler.set_proxy_options)
        
        If the option 'defer_getattr' is True for this proxy, then a new proxy object
        is returned _without_ asking the remote object whether the named attribute exists.
        This can save time when making multiple chained attribute requests,
        but may also defer a possible AttributeError until later, making
        them more difficult to debug.
        """
        prox = self._deferred_attr(attr)
        if self._proxy_options['defer_getattr'] is True:
            return prox
        else:
            return prox._undefer()
    
    def _deferred_attr(self, attr, **kwds):
        """Return a proxy to an attribute of this object. The attribute lookup
        is deferred.
        """
        opts = self._proxy_options.copy()
        opts.update(kwds)
        proxy = ObjectProxy(self._rpc_addr, self._obj_id, self._ref_id, 
                            self._type_str, self._attributes + (attr,), **opts)
        # Keep a reference to the parent proxy so that the remote object cannot be
        # released as long as this proxy is alive.
        proxy.__dict__['_parent_proxy'] = self
        return proxy
    
    def __call__(self, *args, **kwargs):
        """Call the proxied object from the remote process.
        
        All positional and keyword arguments (except those listed below) are
        sent to the remote procedure call. 
        
        In synchronous mode (see parameters below), this method blocks until
        the remote return value has been received, and then returns that value.
        In asynchronous mode, this method returns a :class:`Future` instance
        immediately, which may be used to retrieve the return value later. If
        return is disabled, then the method immediately returns None.
        
        If the remote call raises an exception on the remote process, then this
        method will raise RemoteCallException if in synchronous mode, or calling
        :func:`Future.result()` will raise RemoteCallException if in
        asynchronous mode. If return is disabled, then remote exceptions will
        be ignored.
        
        
        Parameters
        ----------
        _sync:    'off', 'sync', or 'async'
            Set the sync mode for this call. The default value is determined by
            the 'sync' argument to :func:`_set_proxy_options()`.
        _return_type:  'value', 'proxy', or 'auto'
            Set the return type for this call. The default value is determined by
            the 'return_type' argument to :func:`_set_proxy_options()`.
        _timeout: float 
            Set the timeout for this call. The default value is determined by
            the 'timeout' argument to :func:`_set_proxy_options()`.
        
        See also
        --------
        
        RPCClient.call_obj()
        Future
        
        """
        opts = {
            'sync': self._proxy_options['sync'],
            'return_type': self._proxy_options['return_type'],
            'timeout': self._proxy_options['timeout'],
        }
        for k in opts:
            opts[k] = kwargs.pop('_'+k, opts[k])
        return self._client().call_obj(obj=self, args=args, kwargs=kwargs, **opts)

    def __hash__(self):
        """Override __hash__ because we need to avoid comparing remote and local
        hashes.
        """
        #return id(self)
        return self._hash
    
    # Explicitly proxy special methods. Is there a better way to do this??
    
    def __getitem__(self, *args):
        return self._deferred_attr('__getitem__')(*args)
    
    def __setitem__(self, *args):
        return self._deferred_attr('__setitem__')(*args, _sync='off')
        
    def __setattr__(self, *args):
        return self._deferred_attr('__setattr__')(*args, _sync='off')
        
    def __str__(self, *args):
        # for safe printing
        return repr(self)
        #return self._deferred_attr('__str__')(*args, _return_type='value')
        
    def __len__(self, *args):
        return self._deferred_attr('__len__')(*args)
    
    def __add__(self, *args):
        return self._deferred_attr('__add__')(*args)
    
    def __sub__(self, *args):
        return self._deferred_attr('__sub__')(*args)
        
    def __div__(self, *args):
        return self._deferred_attr('__div__')(*args)
        
    def __truediv__(self, *args):
        return self._deferred_attr('__truediv__')(*args)
        
    def __floordiv__(self, *args):
        return self._deferred_attr('__floordiv__')(*args)
        
    def __mul__(self, *args):
        return self._deferred_attr('__mul__')(*args)
        
    def __pow__(self, *args):
        return self._deferred_attr('__pow__')(*args)
        
    def __iadd__(self, *args):
        return self._deferred_attr('__iadd__')(*args, _sync='off')
    
    def __isub__(self, *args):
        return self._deferred_attr('__isub__')(*args, _sync='off')
        
    def __idiv__(self, *args):
        return self._deferred_attr('__idiv__')(*args, _sync='off')
        
    def __itruediv__(self, *args):
        return self._deferred_attr('__itruediv__')(*args, _sync='off')
        
    def __ifloordiv__(self, *args):
        return self._deferred_attr('__ifloordiv__')(*args, _sync='off')
        
    def __imul__(self, *args):
        return self._deferred_attr('__imul__')(*args, _sync='off')
        
    def __ipow__(self, *args):
        return self._deferred_attr('__ipow__')(*args, _sync='off')
        
    def __rshift__(self, *args):
        return self._deferred_attr('__rshift__')(*args)
        
    def __lshift__(self, *args):
        return self._deferred_attr('__lshift__')(*args)
        
    def __irshift__(self, *args):
        return self._deferred_attr('__irshift__')(*args, _sync='off')
        
    def __ilshift__(self, *args):
        return self._deferred_attr('__ilshift__')(*args, _sync='off')
        
    def __eq__(self, *args):
        # If checking equality between two proxies to the same object, then
        # we can immediately return True.
        if (isinstance(args[0], ObjectProxy) and 
            args[0]._rpc_addr == self._rpc_addr and
            args[0]._obj_id == self._obj_id):
            return True
        return self._deferred_attr('__eq__')(*args)
    
    def __ne__(self, *args):
        return self._deferred_attr('__ne__')(*args)
        
    def __lt__(self, *args):
        return self._deferred_attr('__lt__')(*args)
    
    def __gt__(self, *args):
        return self._deferred_attr('__gt__')(*args)
        
    def __le__(self, *args):
        return self._deferred_attr('__le__')(*args)
    
    def __ge__(self, *args):
        return self._deferred_attr('__ge__')(*args)
        
    def __and__(self, *args):
        return self._deferred_attr('__and__')(*args)
        
    def __or__(self, *args):
        return self._deferred_attr('__or__')(*args)
        
    def __xor__(self, *args):
        return self._deferred_attr('__xor__')(*args)
        
    def __iand__(self, *args):
        return self._deferred_attr('__iand__')(*args, _sync='off')
        
    def __ior__(self, *args):
        return self._deferred_attr('__ior__')(*args, _sync='off')
        
    def __ixor__(self, *args):
        return self._deferred_attr('__ixor__')(*args, _sync='off')
        
    def __mod__(self, *args):
        return self._deferred_attr('__mod__')(*args)
        
    def __radd__(self, *args):
        return self._deferred_attr('__radd__')(*args)
    
    def __rsub__(self, *args):
        return self._deferred_attr('__rsub__')(*args)
        
    def __rdiv__(self, *args):
        return self._deferred_attr('__rdiv__')(*args)
        
    def __rfloordiv__(self, *args):
        return self._deferred_attr('__rfloordiv__')(*args)
        
    def __rtruediv__(self, *args):
        return self._deferred_attr('__rtruediv__')(*args)
        
    def __rmul__(self, *args):
        return self._deferred_attr('__rmul__')(*args)
        
    def __rpow__(self, *args):
        return self._deferred_attr('__rpow__')(*args)
        
    def __rrshift__(self, *args):
        return self._deferred_attr('__rrshift__')(*args)
        
    def __rlshift__(self, *args):
        return self._deferred_attr('__rlshift__')(*args)
        
    def __rand__(self, *args):
        return self._deferred_attr('__rand__')(*args)
        
    def __ror__(self, *args):
        return self._deferred_attr('__ror__')(*args)
        
    def __rxor__(self, *args):
        return self._deferred_attr('__ror__')(*args)
        
    def __rmod__(self, *args):
        return self._deferred_attr('__rmod__')(*args)
