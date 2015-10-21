import os
import weakref



"""
proxy options:
    calls/getattrs are sync/async/off
    call args are proxied or autoproxied w/type list
    return values are proxied or autoproxied w/type list
    











ObjectProxy is uniquely identified system-wide by
    1. rpc_id
    2. obj_id
    3. attributes
    (ObjectProxy does not have parent.)

Each unique ObjectProxy can only exist once per thread.

ObjectProxy manages ref counts for all proxies on a per-thread basis
    Need a globally unique identifier for threads:
        GTID = global thread ID     ?
            HOST+PID+TID
        Maybe just use a random ID?
    
Every time a proxy is created, the rpc server must be informed of the GTID that will own the new proxy
    - this means all rpc servers and clients must know the GTID of their endpoints.
        (maybe we should replace `ping` with `ident`)
          srv_gtid = server.send('ident', cli_gtid)

ALL rpc servers should have a proxy to the manager for sending log messages and thread/process failure messages.

Ony one server per thread, and there can be only one client per PID+TID endpoint per thread. Need singleton
management like `get_server()` and `get_client(rpc_id)`



Cases:

    1. server returns locally proxied object to client
        LocalObjectProxy knows GTID of client, registers reference with server.
    2. client sends locally proxied object to server (this implies a locally running server)
        LocalObjectProxy needs to know the GTID of the remote server and register the reference with
        the local server.
    3. client sends proxy to server
        ObjectProxy needs to know the server's GTID and register the reference with the proxy's server.
        This must happen before the proxy is sent.
    4. server returns proxy to client
        ObjectProxy needs to know the client's GTID and register the reference with the proxy's server.
        This must happen before the proxy is sent.
        
    In all of these cases, a proxy that is lost in transit (eg: if there is an unserialization error)
    will cause a reference leak.






"""







#class LocalObjectProxy(object):
    #"""
    #Used for wrapping local objects to ensure that they are send by proxy to a remote host.
    #Note that 'proxy' is just a shorter alias for LocalObjectProxy.
    
    #For example::
    
        #data = [1,2,3,4,5]
        #remotePlot.plot(data)         ## by default, lists are pickled and sent by value
        #remotePlot.plot(proxy(data))  ## force the object to be sent by proxy
    
    #"""
    #def __init__(self, server, obj, attributes=(), **opts):
        #"""
        #Create a 'local' proxy object that, when sent to a remote host,
        #will appear as a normal ObjectProxy to *obj*. 
        #Any extra keyword arguments are passed to proxy._set_proxy_options()
        #on the remote side.
        #"""
        #self.server = weakref.ref(server)
        #self.type_str = repr(obj)
        #self.obj = obj
        #self.attributes = attributes
        #self.opts = opts

    #def save(self):
        #"""Convert this proxy to a serializable structure.
        #"""
        #state = {
            #'rpc_id': self.server().address, 
            #'obj_id': id(self.obj), 
            #'type_str': self.type_str,
            #'attributes': self.attributes,
        #}
        #state.update(self.opts)
        #return state

        
### alias
#proxy = LocalObjectProxy



class ObjectProxy(object):
    """
    Proxy to an object stored by a remote process. Proxies are created
    by calling Process._import(), Process.transfer(), or by requesting/calling
    attributes on existing proxy objects.
    
    For the most part, this object can be used exactly as if it
    were a local object::
    
        rsys = proc._import('sys')   # returns proxy to sys module on remote process
        rsys.stdout                  # proxy to remote sys.stdout
        rsys.stdout.write            # proxy to remote sys.stdout.write
        rsys.stdout.write('hello')   # calls sys.stdout.write('hello') on remote machine
                                     # and returns the result (None)
    
    When calling a proxy to a remote function, the call can be made synchronous
    (result of call is returned immediately), asynchronous (result is returned later),
    or return can be disabled entirely::
    
        ros = proc._import('os')
        
        ## synchronous call; result is returned immediately
        pid = ros.getpid()
        
        ## asynchronous call
        request = ros.getpid(_sync='async')
        while not request.hasResult():
            time.sleep(0.01)
        pid = request.result()
        
        ## disable return when we know it isn't needed
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
    
    """
    
    def __init__(self, rpc_id, obj_id, type_str='', attributes=(), **kwds):
        object.__init__(self)
        ## can't set attributes directly because setattr is overridden.
        self.__dict__['_rpc_id'] = rpc_id
        self.__dict__['_obj_id'] = obj_id
        self.__dict__['_type_str'] = type_str
        self.__dict__['_attributes'] = attributes
        self.__dict__['_parent_proxy'] = None
        
        # identify local client/server instances this proxy might belong to
        from .client import RPCClient
        self.__dict__['_client'] = RPCClient.get_client(self._rpc_id)
        from .server import RPCServer
        self.__dict__['_server'] = RPCServer.get_server()
        
        ## attributes that affect the behavior of the proxy. 
        self.__dict__['_proxy_options'] = {
            'sync': 'sync',      ## 'sync', 'async', 'off'
            'timeout': 10,            ## float
            'return_type': 'auto',    ## 'proxy', 'value', 'auto'
            #'auto_proxy_args': False, ## bool
            'defer_getattr': False,   ## True, False
            'no_proxy_types': [type(None), str, int, float, tuple, list, dict, ObjectProxy],
        }
        
        self._set_proxy_options(**kwds)
    
    def _set_proxy_options(self, **kwds):
        """
        Change the behavior of this proxy. For all options, a value of None
        will cause the proxy to instead use the default behavior defined
        by its parent Process.
        
        Options are:
        
        =============  =============================================================
        sync       'sync', 'async', 'off', or None. 
                       If 'async', then calling methods will return a Request object
                       which can be used to inquire later about the result of the 
                       method call.
                       If 'sync', then calling a method
                       will block until the remote process has returned its result
                       or the timeout has elapsed (in this case, a Request object
                       is returned instead).
                       If 'off', then the remote process is instructed _not_ to 
                       reply and the method call will return None immediately.
        return_type     'auto', 'proxy', 'value', or None. 
                       If 'proxy', then the value returned when calling a method
                       will be a proxy to the object on the remote process.
                       If 'value', then attempt to pickle the returned object and
                       send it back.
                       If 'auto', then the decision is made by consulting the
                       'no_proxy_types' option.
        auto_proxy      bool or None. If True, arguments to __call__ are 
                       automatically converted to proxy unless their type is 
                       listed in no_proxy_types (see below). If False, arguments
                       are left untouched. Use proxy(obj) to manually convert
                       arguments before sending. 
        timeout        float or None. Length of time to wait during synchronous 
                       requests before returning a Request object instead.
        defer_getattr   True, False, or None. 
                       If False, all attribute requests will be sent to the remote 
                       process immediately and will block until a response is
                       received (or timeout has elapsed).
                       If True, requesting an attribute from the proxy returns a
                       new proxy immediately. The remote process is _not_ contacted
                       to make this request. This is faster, but it is possible to 
                       request an attribute that does not exist on the proxied
                       object. In this case, AttributeError will not be raised
                       until an attempt is made to look up the attribute on the
                       remote process.
        no_proxy_types   List of object types that should _not_ be proxied when
                       sent to the remote process.
        =============  =============================================================
        """
        for k in kwds:
            if k not in self._proxy_options:
                raise KeyError("Unrecognized proxy option '%s'" % k)
        self._proxy_options.update(kwds)

    def save(self):
        """Convert this proxy to a serializable structure.
        """
        state = {
            'rpc_id': self._rpc_id, 
            'obj_id': self._obj_id, 
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
        """
        if self._client is None:
            return self._server.unwrap_proxy(self)
        else:
            return self._client.get_obj_value(self)
        
    def __reduce__(self):
        return (unpickleObjectProxy, (self._rpc_id, self._obj_id, self._type_str, self._attributes))
    
    def __repr__(self):
        rep = "<ObjectProxy for process %s, object %d: %s >" % (self._rpc_id, self._obj_id, self._type_str)
        return '.'.join((rep,) + self._attributes)

    def _undefer(self, sync='sync', return_type='auto'):
        """Process any deferred attribute lookups and return the result.
        """
        if len(self._attributes) == 0:
            return self
        # Transfer sends this object to the remote process and returns a new proxy.
        # In the process, this invokes any deferred attributes.
        return self._client.transfer(self, sync=sync, return_type=return_type)
        
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
        proxy = ObjectProxy(self._rpc_id, self._obj_id, self._type_str, self._attributes + (attr,), **opts)
        # Keep a reference to the parent proxy so that the remote object cannot be
        # released as long as this proxy is alive.
        proxy.__dict__['_parent_proxy'] = self
        return proxy
    
    def __call__(self, *args, **kwargs):
        """
        Attempts to call the proxied object from the remote process.
        Accepts extra keyword arguments:
        
            _sync    'off', 'sync', or 'async'
            _return_type  'value', 'proxy', or 'auto'
            _timeout      float 
        
        If the remote call raises an exception on the remote process,
        it will be re-raised on the local process.
        
        """
        opts = {
            'sync': self._proxy_options['sync'],
            'return_type': self._proxy_options['return_type'],
            'timeout': self._proxy_options['timeout'],
        }
        for k in opts:
            opts[k] = kwargs.pop('_'+k, opts[k])
        return self._client.call_obj(obj=self, args=args, kwargs=kwargs, **opts)

    
    # Explicitly proxy special methods. Is there a better way to do this??
    
    def _getSpecialAttr(self, attr):
        # this just gives us an easy way to change the behavior of the special methods
        return self._deferred_attr(attr)
    
    def __getitem__(self, *args):
        return self._getSpecialAttr('__getitem__')(*args)
    
    def __setitem__(self, *args):
        return self._getSpecialAttr('__setitem__')(*args, _sync='off')
        
    def __setattr__(self, *args):
        return self._getSpecialAttr('__setattr__')(*args, _sync='off')
        
    def __str__(self, *args):
        # for safe printing
        return repr(self)
        #return self._getSpecialAttr('__str__')(*args, _return_type='value')
        
    def __len__(self, *args):
        return self._getSpecialAttr('__len__')(*args)
    
    def __add__(self, *args):
        return self._getSpecialAttr('__add__')(*args)
    
    def __sub__(self, *args):
        return self._getSpecialAttr('__sub__')(*args)
        
    def __div__(self, *args):
        return self._getSpecialAttr('__div__')(*args)
        
    def __truediv__(self, *args):
        return self._getSpecialAttr('__truediv__')(*args)
        
    def __floordiv__(self, *args):
        return self._getSpecialAttr('__floordiv__')(*args)
        
    def __mul__(self, *args):
        return self._getSpecialAttr('__mul__')(*args)
        
    def __pow__(self, *args):
        return self._getSpecialAttr('__pow__')(*args)
        
    def __iadd__(self, *args):
        return self._getSpecialAttr('__iadd__')(*args, _sync='off')
    
    def __isub__(self, *args):
        return self._getSpecialAttr('__isub__')(*args, _sync='off')
        
    def __idiv__(self, *args):
        return self._getSpecialAttr('__idiv__')(*args, _sync='off')
        
    def __itruediv__(self, *args):
        return self._getSpecialAttr('__itruediv__')(*args, _sync='off')
        
    def __ifloordiv__(self, *args):
        return self._getSpecialAttr('__ifloordiv__')(*args, _sync='off')
        
    def __imul__(self, *args):
        return self._getSpecialAttr('__imul__')(*args, _sync='off')
        
    def __ipow__(self, *args):
        return self._getSpecialAttr('__ipow__')(*args, _sync='off')
        
    def __rshift__(self, *args):
        return self._getSpecialAttr('__rshift__')(*args)
        
    def __lshift__(self, *args):
        return self._getSpecialAttr('__lshift__')(*args)
        
    def __irshift__(self, *args):
        return self._getSpecialAttr('__irshift__')(*args, _sync='off')
        
    def __ilshift__(self, *args):
        return self._getSpecialAttr('__ilshift__')(*args, _sync='off')
        
    def __eq__(self, *args):
        return self._getSpecialAttr('__eq__')(*args)
    
    def __ne__(self, *args):
        return self._getSpecialAttr('__ne__')(*args)
        
    def __lt__(self, *args):
        return self._getSpecialAttr('__lt__')(*args)
    
    def __gt__(self, *args):
        return self._getSpecialAttr('__gt__')(*args)
        
    def __le__(self, *args):
        return self._getSpecialAttr('__le__')(*args)
    
    def __ge__(self, *args):
        return self._getSpecialAttr('__ge__')(*args)
        
    def __and__(self, *args):
        return self._getSpecialAttr('__and__')(*args)
        
    def __or__(self, *args):
        return self._getSpecialAttr('__or__')(*args)
        
    def __xor__(self, *args):
        return self._getSpecialAttr('__xor__')(*args)
        
    def __iand__(self, *args):
        return self._getSpecialAttr('__iand__')(*args, _sync='off')
        
    def __ior__(self, *args):
        return self._getSpecialAttr('__ior__')(*args, _sync='off')
        
    def __ixor__(self, *args):
        return self._getSpecialAttr('__ixor__')(*args, _sync='off')
        
    def __mod__(self, *args):
        return self._getSpecialAttr('__mod__')(*args)
        
    def __radd__(self, *args):
        return self._getSpecialAttr('__radd__')(*args)
    
    def __rsub__(self, *args):
        return self._getSpecialAttr('__rsub__')(*args)
        
    def __rdiv__(self, *args):
        return self._getSpecialAttr('__rdiv__')(*args)
        
    def __rfloordiv__(self, *args):
        return self._getSpecialAttr('__rfloordiv__')(*args)
        
    def __rtruediv__(self, *args):
        return self._getSpecialAttr('__rtruediv__')(*args)
        
    def __rmul__(self, *args):
        return self._getSpecialAttr('__rmul__')(*args)
        
    def __rpow__(self, *args):
        return self._getSpecialAttr('__rpow__')(*args)
        
    def __rrshift__(self, *args):
        return self._getSpecialAttr('__rrshift__')(*args)
        
    def __rlshift__(self, *args):
        return self._getSpecialAttr('__rlshift__')(*args)
        
    def __rand__(self, *args):
        return self._getSpecialAttr('__rand__')(*args)
        
    def __ror__(self, *args):
        return self._getSpecialAttr('__ror__')(*args)
        
    def __rxor__(self, *args):
        return self._getSpecialAttr('__ror__')(*args)
        
    def __rmod__(self, *args):
        return self._getSpecialAttr('__rmod__')(*args)
        
    def __hash__(self):
        ## Required for python3 since __eq__ is defined.
        return id(self)



