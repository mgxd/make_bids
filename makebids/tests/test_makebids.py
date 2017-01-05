import os
from os.path import join as op

from makebids.makebids import *

#def test_find_subs():
#	dset = os.path.join(DATASETS_PATH, 'ds1')
#	subjs = sorted([x for x in os.listdir(dset) 
#	    	        if '0' in x and 'sub-' not in x])
#	assert len(subjs) == 4

def test_add_sub():
	# return last subject
	last = add_sub(op('datasets', 'ds1'), '0', live=False).split(os.sep)[-1]
	assert last == 'sub-04'