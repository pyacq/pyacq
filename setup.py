# -*- coding: utf-8 -*-

from setuptools import setup, find_packages
import os
import pyacq


long_description = """
Pyacq is a simple, pure-Python framework for distributed data acquisition and
stream processing. Its primary use cases are for analog signals, digital
signals, video, and events. Pyacq uses ZeroMQ to stream data between
distributed threads, processes, and machines to build more complex and
scalable acquisition systems.
"""


setup(
    name = "pyacq",
    version = pyacq.__version__,
    packages = ['pyacq.' + pkg for pkg in find_packages('pyacq')],
    install_requires=[
                    'numpy',
                    'pyzmq',
                    'pyqtgraph',
                    #'blosc',  # optional; causes install failure on appveyor
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



 
