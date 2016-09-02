'''
script to facilitate conversion to BIDS format (http://bids.neuroimaging.io)
use intended after converting dicom to nifti with dcm2niix using heudiconv (https://github.com/nipy/heudiconv)
'''

import shutil
import os
from glob import glob
import csv
import sys
import json

class BidsFileStructure:
    def __init__(self, path):
        self.path = path
    
    def has_ses(self):
        return 'ses' in self.path
    
    def taskname(self):
        if 'task' in self.path:
            return self.path.split('_task-')[-1].split('_')[0]
    
    def subjprefix(self):
        return filter(lambda x: not x.isdigit(), self.path.split('sub-')[-1].split('_')[0])

def load_json(filename):
    with open(filename, 'r') as fp:
        data = json.load(fp)
    return data

def add_sub(data_dir, subjpre, ses, no_test):
    subjs = [x for x in sorted(os.listdir(data_dir)) if subjpre in x and 'sub-' not in x]
    for subj in subjs:
        old = os.path.join(data_dir, subj)
        new = os.path.join(data_dir, 'sub-' + subj)
        print(old + ' will become ' + new)
        if no_test:
            os.rename(old, new)

def drop_underscore(data_dir, subjpre, no_test, undscr=1, ses=None):
    # initial directories
    os.chdir(data_dir)
    for _dir in os.listdir(data_dir) + os.listdir(os.path.join(data_dir,'sourcedata')):
        if subjpre in _dir:
            splt = _dir.split('_')
            new = ''.join(splt[:(undscr+1)])
            print("Changing " + os.path.abspath(_dir) + " to " + os.path.abspath(new))
            if no_test:
                os.rename(os.path.abspath(_dir),os.path.abspath(new))
    #rest of files
    try:
        for dirs in glob(os.path.join(data_dir,'*','*')):
            files = os.listdir(dirs)
            for f in files:
                if subjpre in f:
                    os.chdir(dirs)
                    splt = f.split('_')
                    new = ''.join(splt[:(undscr+1)]) + '_' + '_'.join(splt[(undscr+1):])
                    # no point in having files end with underscores
                    if new[-1] == '_':
                        new = new[:-1]
                    print("Changing " + f + " to " + new)
                    if no_test:
                        os.rename(f,new)
    except:
        raise IOError('Sessions are not yet supported')
                    
def write_scantsv(bids_dir, dicom_dir, pre, no_test):
    subs = sorted([x[-3:] for x in os.listdir(bids_dir) if 'sub-' in x])
    for sid in subs:
        dcm = dicom.read_file(glob(os.path.join(dicom_dir,'*' + sid, '*', '*'))[-1], force=True)
        date = dcm.AcquisitionDate[:4] + '-' + dcm.AcquisitionDate[4:6] + '-' + dcm.AcquisitionDate[6:]
        scans = []
        for scan in glob(os.path.join(bids_dir, '*' + sid, '*', '*.nii.gz')):
            paths = scan.split('/')
            scans.append('/'.join(paths[-2:]))
            outname = os.path.join(bids_dir, paths[-3], paths[-3]+'_scans.tsv')
        if no_test:
            with open(outname, 'wt') as tsvfile:
                writer = csv.writer(tsvfile, delimiter='\t')
                writer.writerow(['filename', 'acq_time'])
                for scan in sorted(scans):
                    writer.writerow([scan, date])
            print('Wrote %s'%outname)
    print(date)

def add_taskname(bids_dir, taskname, no_test):
    for scan in glob(os.path.join(bids_dir, '*', '*', '*task*_bold.json')):
        if taskname in scan:
            prev = load_json(scan)
            comb = dict(prev.items() + {'TaskName': '%s'%taskname}.items())
            if no_test:
                with open(scan, 'wt') as fp:
                    json.dump(comb, fp, indent=0, sort_keys=True)

def groupSes(subjs,ls,xdir):
    for sub in subjs:
        subpath = os.path.join(xdir,'sub-' + sub)
        if not os.path.exists(subpath):
            print("Making " + subpath + "...")
            #os.makedirs(subpath)
        for dr in ls:
            if 'SESSION' in dr:
                sid = "sub-" + dr[:4]
                if sid == sub:
                    print("Starting to move " + dr + " to " + subpath + "...")
                    #shutil.move(os.path.join(xdir,dr),subpath)
                    print(dr + " was moved to " + subpath)

def remove_extra(xdir, xtra):
    for x in glob(os.path.join(xdir, '*', '*', '*')):
        fls = os.listdir(x)
        for fl in fls:
            if xtra in fl:
                os.chdir(x)
                fp = os.path.realpath(fl)
                new = os.path.join(os.path.dirname(fp),"".join(fl.split(xtra)))

def makebids(data_dir, subjpre, dicom_dir=None, session=None, taskname=None, no_test=False):
    choice = int(raw_input('''
Pick one option:
1. Add sub prefix
2. Remove underscore
3. Make subject scan files
4. Add taskname to json
'''))
    if choice == 1:
        add_sub(data_dir, subjpre, session, no_test)
    if choice == 2:
        undscr = int(raw_input('''How many underscores in your subject?\n'''))
        drop_underscore(data_dir, subjpre, no_test, undscr)
    if choice == 3:
        try:
            import dicom
        except ImportError:
            print('You need to have pydicom installed')
            sys.exit(-1)
        if not dicom_dir:
            print('Specify dicom directory with [-d] flag')
            sys.exit(-1)
        write_scantsv(data_dir, dicom_dir, subjpre, no_test)
    if choice == 4:
        add_taskname(data_dir, taskname, no_test)
    else:
        sys.exit(-1)
        
if __name__ == '__main__':
    import argparse
    defstr = ' (default %(default)s)'
    parser = argparse.ArgumentParser(prog='make_bids.py')
    parser.add_argument('datadir', help='''bids-like directory''')
    parser.add_argument('pre', type=str, help='''subject identifier (no numbers)''')
    parser.add_argument('--ses', type=int, dest='session')
    parser.add_argument('-d', '--dicoms', type=str, help='''dicom directory''')
    parser.add_argument('-t', '--taskname', type=str, help='''task name''')
    parser.add_argument('--notest', action='store_true')
    args = parser.parse_args()
    if args.dicoms:
        import dicom
    if args.dicoms:
        args.dicoms = os.path.abspath(args.dicoms)
    no_test = args.notest
    if no_test is None:
        no_test = False
    makebids(data_dir=os.path.abspath(args.datadir),
             subjpre=args.pre,
             dicom_dir=args.dicoms,
             session=args.session, taskname=args.taskname,
             no_test=no_test)

