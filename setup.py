#!/usr/bin/env python
# vi: set ft=python sts=4 ts=4 sw=4 et:

import os
from setuptools import setup

here = os.path.abspath(os.path.dirname(__file__))

setup(name='makebids',
      version='dev',
      url='https://github.com/mgxd/makebids',
      author='Mathias Goncalves',
      author_email='mathiasg@mit.edu',
      packages=['makebids'],
      install_requires = ['pydicom'],
      entry_points={'console_scripts': 
                 ['makebids=makebids.makebids:main']})
