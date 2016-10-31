#!/usr/bin/env python
# emacs: -*- mode: python; py-indent-offset: 4; indent-tabs-mode: nil -*-
# vi: set ft=python sts=4 ts=4 sw=4 et:
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

from bids.grabbids import BIDSLayout

def load_json(filename):
    with open(filename, 'r') as fp:
        data = json.load(fp)
    return data

def add_metadata(infofile, add):
    """Adds dict items to exisiting json
    Parameters
    ----------
    json : str (path to json file)
    add : dict (items to add)
    Returns
    ----------
    Nothing
    """
    meta = load_json(infofile)
    meta_info = dict(meta.items() + add.items())
    with open(infofile, 'wt') as fp:
        json.dump(meta_info, fp, indent=1, sort_keys=True)
    return infofile

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

def fix_fieldmaps(bids_dir, no_test=False):
    layout = BIDSLayout(bids_dir)
    fmaps = [f.filename for f in layout.get(ext='.json', type='epi')]
    bn = lambda x: os.path.basename(x)
    for fmap in fmaps:
        print('Fieldmap: ' + bn(fmap).split('.json')[0])
        subj = bn(fmap).split('_')[0]
        dr = search('(?<=acq-)\w+', os.path.basename(fmap).replace('_', ' ')).group(0)
        niftis = [n.filename for n in layout.get(
            subject='%s'% subj.split('sub-')[-1],
            extensions='.nii.gz') if dr in n.filename and 'fmap' not in n.filename]
        # Add intended to all functionals
        if 'func' in dr:
            choice = [x.split('%s/'%subj)[-1] for x in niftis]
        else:
            choice = choose(niftis,fmap).split('%s/'%subj)[-1]
        readout = calc_readout(load_json(fmap))
        #return meta.keys()
        add = {'IntendedFor': choice,
               'TotalReadoutTime': readout}
        if no_test:
            add_metadata(fmap, add)
        return

def calc_readout(meta):
    """Calculate readout time
    Parameters
    ----------
    meta - dict (json from dcm2niix)
    Returns
    ----------
    readout - float"""
    return ((meta['global']['const']['AcquisitionMatrix'][0] - 1) \
            * meta['EffectiveEchoSpacing'])

def choose(opts, target=None):
    """Print out list and takes selection
    Parameters
    ----------
    opts : list (of choices)
    target : str (to compare)
    Returns
    ----------
    choice: item"""
    ratio = 0
    match = None
    if target:
        for i, opt in enumerate(opts):
            compare = lambda x,y: SequenceMatcher(None, x, y).ratio()
            sim = compare(os.path.basename(opt), os.path.basename(target))
            if sim > ratio:
                ratio,match = sim,opt
        print("Best match: %s\n"%(os.path.basename(match)))
        return match
        #if raw_input("Closest find:%s\n\n(y/n)" \
        #             %os.path.basename(match)).lower() == 'y':
        #    return match
    for i, opt in enumerate(opts,1):
        print(str(i)+') '+ os.path.basename(opt))
    choice = int(raw_input('\nInput number\n'))
    while choice > len(opts) or choice < 1:
        print('Out of range')
        choice = int(raw_input('\nInput number\n'))
    return opts[choice-1]

def main():
    import argparse
    defstr = ' (default %(default)s)'
    parser = argparse.ArgumentParser(prog='makebids.py',
                                     description=__doc__)
    parser.add_argument('datadir', help='''bids-like directory''')
    parser.add_argument('pre', type=str, help='''subject identifier (no numbers)''')
    parser.add_argument('--ses', type=int, dest='session')
    parser.add_argument('-d', '--dicoms', type=str, help='''dicom directory''')
    parser.add_argument('-t', '--taskname', type=str, help='''task name''')
    parser.add_argument('--notest', action='store_true')
    args = parser.parse_args()
    if args.dicoms:
        import dicom
        dicom_dir = os.path.abspath(args.dicoms)
    no_test = args.notest
    if no_test is None:
        no_test = False

    data_dir = os.path.abspath(args.datadir)
    if not os.path.exists(data_dir):
        print('Data directory not found')
        sys.exit(-1)

    choice = int(raw_input('''
Choose an option:
1. Add sub prefix
2. Remove underscore
3. Make subject scan files
4. Add taskname to json
5. Add IntendedFor / Readout
'''))
    if choice == 1:
        add_sub(data_dir, args.pre, args.session, no_test)
    elif choice == 2:
        undscr = int(raw_input('''How many underscores in your subject?\n'''))
        drop_underscore(data_dir, args.pre, no_test, undscr)
    elif choice == 3:
        if args.dicom_dir:
            write_scantsv(data_dir, dicom_dir, args.pre, no_test)
        else:
            print('Specify dicom directory with [-d] flag')
            sys.exit(-1)
    elif choice == 4:
        add_taskname(data_dir, args.taskname, no_test)
    elif choice == 5:
        fix_fieldmaps(data_dir, no_test)
    else:
        sys.exit(-1)
        
if __name__ == '__main__':
    main()
