from os.path import join as opj

from makebids.makebids import *

# add to package
DATASETS = '../../datasets/'

msg = '{0} will become {1}'

#def test_find_subs():
#	dset = os.path.join(DATASETS_PATH, 'ds1')
#	subjs = sorted([x for x in os.listdir(dset) 
#	    	        if '0' in x and 'sub-' not in x])
#	assert len(subjs) == 4

def test_add_sub():
	add_sub(opj(DATASETS, 'ds1'), '0')

if __name__ == '__main__':
	test_add_sub()