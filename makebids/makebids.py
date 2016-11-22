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
import argparse
import re

import dicom
from bids.grabbids import BIDSLayout

OPTIONS = '''
1. Add sub prefix
2. Remove underscore
3. Make subject scan files
4. Add taskname to json
5. Add IntendedFor / Readout
'''

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
        json.dump(meta_info, fp, indent=4, sort_keys=True)
    return infofile

def add_sub(data_dir, subjpre, live=False):
    """Add BIDS sub- prefix to subjects converted with heudiconv"""
    subjs = sorted([x for x in os.listdir(data_dir) if subjpre in x 
                                            and 'sub-' not in x])
    for subj in subjs:
        old = os.path.join(data_dir, subj)
        new = os.path.join(data_dir, 'sub-' + subj)
        if live:
            os.rename(old, new)
        else:
            print(msg.format(old, new))

def drop_underscore(data_dir, live=False):
    """ Change directories first, then files """
    subjs = sorted([x for x in os.listdir(data_dir) if x.startswith('sub-')])
    for subj in subjs:
        if subj.count('_') == 0:
            continue
        corr = subj.replace('_', '')
        if live:
            os.rename(op(data_dir, subj), op(data_dir, corr))
        else:
            print(msg.format(op(data_dir, subj), op(data_dir, corr)))
            return
        # refresh after each rename
        layout = BIDSLayout(data_dir)
        files = [f.filename for f in layout.get() if subj in f.filename]
        for file in files:
            fix = file.replace(subj, corr)
            os.rename(file, fix)
                    
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

def add_taskname(bids_dir, taskname, live=False):
    for scan in glob(os.path.join(bids_dir, '*', '*', '*task*_bold.json')):
        if taskname in scan:
            prev = load_json(scan)
            comb = dict(prev.items() + {'TaskName': '%s'%taskname}.items())
            if live:
                os.chmod(scan, 0o640)
                with open(scan, 'wt') as fp:
                    json.dump(comb, fp, indent=0, sort_keys=True)
                os.chmod(scan, 0o440)
                    
def fix_fieldmaps(layout, live=False):
    fmaps = [f.filename for f in layout.get(ext='.json', type='epi')]
    bn = lambda x: os.path.basename(x)
    for fmap in fmaps:
        print('Fieldmap: ' + bn(fmap).split('.json')[0])
        subj = bn(fmap).split('_')[0]
        try:
            pe = re.search('(?<=acq-)\w+', os.path.basename(fmap).replace('_', ' ')).group(0)
        except AttributeError: # dir or acq
            pe = re.search('(?<=dir-)\w+', os.path.basename(fmap).replace('_', ' ')).group(0)
        except:
            continue
        # all niftis with that phase encoding
        niftis = [n.filename for n in layout.get(
                  subject='%s'% subj.split('sub-')[-1], extensions='.nii.gz') 
                  if pe in n.filename and 'fmap' not in n.filename 
                  and 'derivatives' not in n.filename]
        # relative path within bids dataset
        rel_niftis = [nif.split('{}/'.format(subj))[-1] for nif in niftis]
        # Add intended to all functionals
        readout = calc_readout(load_json(fmap))
        #return meta.keys()
        add = {'IntendedFor': rel_niftis,
               'TotalReadoutTime': readout}
        if live:
            # make writeable and then readonly
            os.chmod(fmap, 0o640)
            add_metadata(fmap, add)
            os.chmod(fmap, 0o440)
        else:
            print('Adding:\n --- ' + '\n --- '.join(rel_niftis))
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

def main():
    # to run in commandline
    class MyParser(argparse.ArgumentParser):
        def error(self, message):
            sys.stderr.write('error: %s\n' % message)
            self.print_help()
            sys.exit(2)

    defstr = ' (default %(default)s)'
    parser = argparse.ArgumentParser(prog='makebids.py',
                                     description=__doc__)
    parser.add_argument('datadir', help='''bids-like directory''')
    parser.add_argument('pre', type=str, help='''subject identifier (no numbers)''')
    parser.add_argument('--ses', type=int, dest='session')
    parser.add_argument('-d', '--dicoms', type=str, default=None, 
                        help="""dicom directory""")
    parser.add_argument('-t', '--taskname', type=str, help="""task name""")
    parser.add_argument('--live', default=False, action='store_true',
                        help="""WARNING: DON'T INCLUDE ON FIRST PASS""")
    parser.add_argument('--full', action='store_true', default=False,
                        help="""run through each option""")
    args = parser.parse_args()
    bids_dir = os.path.abspath(args.datadir)
    if not os.path.exists(bids_dir):
        sys.exit('Specify valid BIDS data directory')
    if args.dicoms:
        dicom_dir = os.path.abspath(args.dicoms)
    else:
        dicom_dir = None

    if args.full:
        add_sub(bids_dir, args.pre, live)
        drop_underscore(bids_dir, live)
        # using BIDS grabbids after renaming files
        layout = BIDSLayout(bids_dir)
        write_scantsv(layout, dicom_dir, live)
        add_taskname(layout, live)
        fix_fieldmaps(layout, live)
    else:
        choice = int(raw_input(OPTIONS))
        if choice == 1:
            add_sub(data_dir, args.pre, live)
        elif choice == 2:
            drop_underscore(data_dir, live)
        elif choice == 3:
            write_scantsv(data_dir, dicom_dir, args.pre, live)
        elif choice == 4:
            add_taskname(data_dir, args.taskname, no_test)
        elif choice == 5:
            fix_fieldmaps(data_dir, no_test)
        else:
            sys.exit('Option not recognized')
        
if __name__ == '__main__':
    main()
