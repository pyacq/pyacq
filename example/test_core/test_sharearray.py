# -*- coding: utf-8 -*-
"""
"""

from pyacq.core.tools import SharedArray

import pickle



def test1():
    
    sa = SharedArray(10, 'float64')
    a = sa.to_numpy_array()
    print a
    
    print len(pickle.dumps(a))
    print pickle.dumps(sa)
    



if __name__ == '__main__':
    test1()

