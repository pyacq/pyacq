# -*- coding: utf-8 -*-

from setuptools import setup
import os

long_description = open("README.rst").read()
import pyacq

setup(
    name = "pyacq",
    version = pyacq.__version__,
    packages = ['pyacq', 'pyacq.core', 'pyacq.core.rpc', 'pyacq.core.rpc.log', 'pyacq.viewers', 'pyacq.devices', 'pyacq.dsp'],
    install_requires=[
                    'numpy',
                    'pyzmq',
                    'pyqtgraph',
                    'blosc',
                    
                    #'msgpack-python',
                    ],
    author = "S.Garcia",
    author_email = "sam.garcia.die@gmail.com",
    description = "Simple Framework for data acquisition (signal, video) in pure python.",
    long_description = long_description,
    license = "BSD",
    url='https://github.com/pyacq/pyacq',
    classifiers = [
        'Development Status :: 4 - Beta',
        'Intended Audience :: Science/Research',
        'License :: OSI Approved :: BSD License',
        'Natural Language :: English',
        'Operating System :: OS Independent',
        'Programming Language :: Python :: 3',
        'Topic :: Scientific/Engineering']
)



 
