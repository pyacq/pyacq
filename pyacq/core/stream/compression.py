compression_methods = ['']


_blosc_methods = ['blosc-blosclz', 'blosc-lz4']
try:
    import blosc
    HAVE_BLOSC = True
    compression_methods.extend(_blosc_methods)
except ImportError:
    HAVE_BLOSC = False


def compress(data, method, *args, **kwds):
    if method == '':
        return data
    _check_method(method)
    
    if method.startswith('blosc-'):
        kwds['cname'] = method[6:]
        data = blosc.compress(data, *args, **kwds)
    else:
        raise ValueError("Unknown compression method '%s'" % method)
    
    return data


def decompress(data, method, *args, **kwds):
    if method == '':
        return data
    _check_method(method)
    
    if method.startswith('blosc-'):
        return blosc.decompress(data)
    else:
        raise ValueError("Unknown compression method '%s'" % method)


def _check_method(method):
    if method not in compression_methods:
        if method in _blosc_methods:
            raise ValueError("Cannot use %s compression; blosc package is not importable." % method)
        else:
            raise ValueError('Unknown compression method "%s"' % method)
