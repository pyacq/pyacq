import os


class LocalObjectProxy(object):
    """
    Used for wrapping local objects to ensure that they are send by proxy to a remote host.
    Note that 'proxy' is just a shorter alias for LocalObjectProxy.
    
    For example::
    
        data = [1,2,3,4,5]
        remotePlot.plot(data)         ## by default, lists are pickled and sent by value
        remotePlot.plot(proxy(data))  ## force the object to be sent by proxy
    
    """
    next_proxy_id = 0
    proxied_objects = {}  ## maps {proxyId: object}
    
    
    @classmethod
    def registerObject(cls, obj):
        ## assign it a unique ID so we can keep a reference to the local object
        
        pid = cls.next_proxy_id
        cls.next_proxy_id += 1
        cls.proxied_objects[pid] = obj
        #print "register:", cls.proxied_objects
        return pid
    
    @classmethod
    def lookupProxyId(cls, pid):
        return cls.proxied_objects[pid]
    
    @classmethod
    def releaseProxyId(cls, pid):
        del cls.proxied_objects[pid]
        #print "release:", cls.proxied_objects 
    
    def __init__(self, obj, **opts):
        """
        Create a 'local' proxy object that, when sent to a remote host,
        will appear as a normal ObjectProxy to *obj*. 
        Any extra keyword arguments are passed to proxy._setProxyOptions()
        on the remote side.
        """
        self.processId = os.getpid()
        #self.objectId = id(obj)
        self.typeStr = repr(obj)
        #self.handler = handler
        self.obj = obj
        self.opts = opts
        
    def __reduce__(self):
        ## a proxy is being pickled and sent to a remote process.
        ## every time this happens, a new proxy will be generated in the remote process,
        ## so we keep a new ID so we can track when each is released.
        pid = LocalObjectProxy.registerObject(self.obj)
        return (unpickleObjectProxy, (self.processId, pid, self.typeStr, None, self.opts))

        
## alias
proxy = LocalObjectProxy


def unpickleObjectProxy(processId, proxyId, typeStr, attributes=None, opts=None):
    if processId == os.getpid():
        obj = LocalObjectProxy.lookupProxyId(proxyId)
        if attributes is not None:
            for attr in attributes:
                obj = getattr(obj, attr)
        return obj
    else:
        proxy = ObjectProxy(processId, proxyId=proxyId, typeStr=typeStr)
        if opts is not None:
            proxy._setProxyOptions(**opts)
        return proxy


class ObjectProxy(object):
    """
    Proxy to an object stored by the remote process. Proxies are created
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
        request = ros.getpid(_callSync='async')
        while not request.hasResult():
            time.sleep(0.01)
        pid = request.result()
        
        ## disable return when we know it isn't needed
        rsys.stdout.write('hello', _callSync='off')
    
    Additionally, values returned from a remote function call are automatically
    returned either by value (must be picklable) or by proxy. 
    This behavior can be forced::
    
        rnp = proc._import('numpy')
        arrProxy = rnp.array([1,2,3,4], _returnType='proxy')
        arrValue = rnp.array([1,2,3,4], _returnType='value')
    
    The default callSync and returnType behaviors (as well as others) can be set 
    for each proxy individually using ObjectProxy._setProxyOptions() or globally using 
    proc.setProxyOptions(). 
    
    """
    def __init__(self, rpc_id, obj_id, type_str='', parent=None):
        object.__init__(self)
        ## can't set attributes directly because setattr is overridden.
        self.__dict__['_rpc_id'] = rpc_id
        self.__dict__['_type_str'] = type_str
        self.__dict__['_obj_id'] = obj_id
        self.__dict__['_attributes'] = ()
        ## attributes that affect the behavior of the proxy. 
        ## in all cases, a value of None causes the proxy to ask
        ## its parent event handler to make the decision
        self.__dict__['_proxy_options'] = {
            'callSync': None,      ## 'sync', 'async', None 
            'timeout': None,       ## float, None
            'returnType': None,    ## 'proxy', 'value', 'auto', None
            'deferGetattr': None,  ## True, False, None
            'noProxyTypes': None,  ## list of types to send by value instead of by proxy
            'autoProxy': None,
        }
        
        self.__dict__['_handler'] = RemoteEventHandler.getHandler(processId)
        self.__dict__['_handler'].registerProxy(self)  ## handler will watch proxy; inform remote process when the proxy is deleted.
    
    def _setProxyOptions(self, **kwds):
        """
        Change the behavior of this proxy. For all options, a value of None
        will cause the proxy to instead use the default behavior defined
        by its parent Process.
        
        Options are:
        
        =============  =============================================================
        callSync       'sync', 'async', 'off', or None. 
                       If 'async', then calling methods will return a Request object
                       which can be used to inquire later about the result of the 
                       method call.
                       If 'sync', then calling a method
                       will block until the remote process has returned its result
                       or the timeout has elapsed (in this case, a Request object
                       is returned instead).
                       If 'off', then the remote process is instructed _not_ to 
                       reply and the method call will return None immediately.
        returnType     'auto', 'proxy', 'value', or None. 
                       If 'proxy', then the value returned when calling a method
                       will be a proxy to the object on the remote process.
                       If 'value', then attempt to pickle the returned object and
                       send it back.
                       If 'auto', then the decision is made by consulting the
                       'noProxyTypes' option.
        autoProxy      bool or None. If True, arguments to __call__ are 
                       automatically converted to proxy unless their type is 
                       listed in noProxyTypes (see below). If False, arguments
                       are left untouched. Use proxy(obj) to manually convert
                       arguments before sending. 
        timeout        float or None. Length of time to wait during synchronous 
                       requests before returning a Request object instead.
        deferGetattr   True, False, or None. 
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
        noProxyTypes   List of object types that should _not_ be proxied when
                       sent to the remote process.
        =============  =============================================================
        """
        for k in kwds:
            if k not in self._proxy_options:
                raise KeyError("Unrecognized proxy option '%s'" % k)
        self._proxy_options.update(kwds)
    
    def _getValue(self):
        """
        Return the value of the proxied object
        (the remote object must be picklable)
        """
        return self._handler.getObjValue(self)
        
    def _getProxyOption(self, opt):
        val = self._proxy_options[opt]
        if val is None:
            return self._handler.getProxyOption(opt)
        return val
    
    def _getProxyOptions(self):
        return dict([(k, self._getProxyOption(k)) for k in self._proxy_options])
    
    def __reduce__(self):
        return (unpickleObjectProxy, (self._processId, self._proxyId, self._typeStr, self._attributes))
    
    def __repr__(self):
        return "<ObjectProxy for process %d, object 0x%x: %s >" % (self._processId, self._proxyId, self._typeStr)
        
    def __getattr__(self, attr, **kwds):
        """
        Calls __getattr__ on the remote object and returns the attribute
        by value or by proxy depending on the options set (see
        ObjectProxy._setProxyOptions and RemoteEventHandler.setProxyOptions)
        
        If the option 'deferGetattr' is True for this proxy, then a new proxy object
        is returned _without_ asking the remote object whether the named attribute exists.
        This can save time when making multiple chained attribute requests,
        but may also defer a possible AttributeError until later, making
        them more difficult to debug.
        """
        opts = self._getProxyOptions()
        for k in opts:
            if '_'+k in kwds:
                opts[k] = kwds.pop('_'+k)
        if opts['deferGetattr'] is True:
            return self._deferredAttr(attr)
        else:
            return self._handler.getObjAttr(self, attr, **opts)
    
    def _deferredAttr(self, attr):
        return DeferredObjectProxy(self, attr)
    
    def __call__(self, *args, **kwds):
        """
        Attempts to call the proxied object from the remote process.
        Accepts extra keyword arguments:
        
            _callSync    'off', 'sync', or 'async'
            _returnType   'value', 'proxy', or 'auto'
        
        If the remote call raises an exception on the remote process,
        it will be re-raised on the local process.
        
        """
        opts = self._getProxyOptions()
        for k in opts:
            if '_'+k in kwds:
                opts[k] = kwds.pop('_'+k)
        return self._handler.callObj(obj=self, args=args, kwds=kwds, **opts)
    
    
    # Explicitly proxy special methods. Is there a better way to do this??
    
    def _getSpecialAttr(self, attr):
        # this just gives us an easy way to change the behavior of the special methods
        return self._deferredAttr(attr)
    
    def __getitem__(self, *args):
        return self._getSpecialAttr('__getitem__')(*args)
    
    def __setitem__(self, *args):
        return self._getSpecialAttr('__setitem__')(*args, _callSync='off')
        
    def __setattr__(self, *args):
        return self._getSpecialAttr('__setattr__')(*args, _callSync='off')
        
    def __str__(self, *args):
        return self._getSpecialAttr('__str__')(*args, _returnType='value')
        
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
        return self._getSpecialAttr('__iadd__')(*args, _callSync='off')
    
    def __isub__(self, *args):
        return self._getSpecialAttr('__isub__')(*args, _callSync='off')
        
    def __idiv__(self, *args):
        return self._getSpecialAttr('__idiv__')(*args, _callSync='off')
        
    def __itruediv__(self, *args):
        return self._getSpecialAttr('__itruediv__')(*args, _callSync='off')
        
    def __ifloordiv__(self, *args):
        return self._getSpecialAttr('__ifloordiv__')(*args, _callSync='off')
        
    def __imul__(self, *args):
        return self._getSpecialAttr('__imul__')(*args, _callSync='off')
        
    def __ipow__(self, *args):
        return self._getSpecialAttr('__ipow__')(*args, _callSync='off')
        
    def __rshift__(self, *args):
        return self._getSpecialAttr('__rshift__')(*args)
        
    def __lshift__(self, *args):
        return self._getSpecialAttr('__lshift__')(*args)
        
    def __irshift__(self, *args):
        return self._getSpecialAttr('__irshift__')(*args, _callSync='off')
        
    def __ilshift__(self, *args):
        return self._getSpecialAttr('__ilshift__')(*args, _callSync='off')
        
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
        return self._getSpecialAttr('__iand__')(*args, _callSync='off')
        
    def __ior__(self, *args):
        return self._getSpecialAttr('__ior__')(*args, _callSync='off')
        
    def __ixor__(self, *args):
        return self._getSpecialAttr('__ixor__')(*args, _callSync='off')
        
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

        
class DeferredObjectProxy(ObjectProxy):
    """
    This class represents an attribute (or sub-attribute) of a proxied object.
    It is used to speed up attribute requests. Take the following scenario::
    
        rsys = proc._import('sys')
        rsys.stdout.write('hello')
        
    For this simple example, a total of 4 synchronous requests are made to 
    the remote process: 
    
    1) import sys
    2) getattr(sys, 'stdout')
    3) getattr(stdout, 'write')
    4) write('hello')
    
    This takes a lot longer than running the equivalent code locally. To
    speed things up, we can 'defer' the two attribute lookups so they are
    only carried out when neccessary::
    
        rsys = proc._import('sys')
        rsys._setProxyOptions(deferGetattr=True)
        rsys.stdout.write('hello')
        
    This example only makes two requests to the remote process; the two 
    attribute lookups immediately return DeferredObjectProxy instances 
    immediately without contacting the remote process. When the call 
    to write() is made, all attribute requests are processed at the same time.
    
    Note that if the attributes requested do not exist on the remote object, 
    making the call to write() will raise an AttributeError.
    """
    def __init__(self, parentProxy, attribute):
        ## can't set attributes directly because setattr is overridden.
        for k in ['_processId', '_typeStr', '_proxyId', '_handler']:
            self.__dict__[k] = getattr(parentProxy, k)
        self.__dict__['_parent'] = parentProxy  ## make sure parent stays alive
        self.__dict__['_attributes'] = parentProxy._attributes + (attribute,)
        self.__dict__['_proxy_options'] = parentProxy._proxy_options.copy()
    
    def __repr__(self):
        return ObjectProxy.__repr__(self) + '.' + '.'.join(self._attributes)
    
    def _undefer(self):
        """
        Return a non-deferred ObjectProxy referencing the same object
        """
        return self._parent.__getattr__(self._attributes[-1], _deferGetattr=False)


