# -*- coding: utf-8 -*-

from setuptools import setup
import os

long_description = open("README.rst").read()
import pyacq

setup(
    name = "pyacq",
    version = pyacq.__version__,
    packages = ['pyacq', ],
    install_requires=[
                    'numpy',
                    'pyzmq',
                    #~ 'gevent',
                    'msgpack-python',
                    'blosc',
                    ],
    author = "S.Garcia",
    author_email = "sgarcia at olfac.univ-lyon1.fr",
    description = "Simple Framework for data acquisition (signal, video) in pure python.",
    long_description = long_description,
    license = "BSD",
    url='http://neuralensemble.org/neo',
    classifiers = [
        'Development Status :: 4 - Beta',
        'Intended Audience :: Science/Research',
        'License :: OSI Approved :: BSD License',
        'Natural Language :: English',
        'Operating System :: OS Independent',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 3',
        'Topic :: Scientific/Engineering']
)



 
