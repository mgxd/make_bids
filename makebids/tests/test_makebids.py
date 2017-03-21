import os
from os.path import join, dirname

from makebids.makebids import *

DATASETS = join(dirname(__file__), 'datasets')

def test_add_sub():
	# return last subject
	subjs = add_sub(join(DATASETS, 'ds1'), '0', 
		           live=False)
	assert subjs == ['01', '02', '03', '04']
	
