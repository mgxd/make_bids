import os
from os.path import join, dirname

from makebids.makebids import *

DATASETS = join(dirname(__file__), 'datasets')

def test_add_sub():
	# return last subject
	last = add_sub(join(DATASETS, 'ds1'), '0', 
		           live=False).split(os.sep)[-1]
	assert last == 'sub-04'