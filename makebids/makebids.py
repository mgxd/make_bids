#!/usr/bin/env python
# emacs: -*- mode: python; py-indent-offset: 4; indent-tabs-mode: nil -*-
# vi: set ft=python sts=4 ts=4 sw=4 et:
'''
script to facilitate conversion to BIDS format (http://bids.neuroimaging.io)
use intended after converting dicom to nifti with dcm2niix using heudiconv (https://github.com/nipy/heudiconv)
'''

import shutil
import os
from os.path import join as op
from glob import glob
import csv
import sys
import json
import argparse
import logging
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

msg = '{0} will become {1}'

def load_json(filename):
    """ easy load of json dict """
    with open(filename, 'r') as fp:
        data = json.load(fp)
    return data

def add_metadata(infofile, add, ind=4):
    """Adds dict items to exisiting json
    Parameters
    ----------
    json : File (path to json file)
    add : dict (items to add)
    ind: indent amount for prettier print
    Returns
    ----------
    Metadata json
    """
    os.chmod(infofile, 0o640)
    meta = load_json(infofile)
    meta_info = dict(meta.items() + add.items())
    with open(infofile, 'wt') as fp:
        json.dump(meta_info, fp, indent=ind, sort_keys=True)
    os.chmod(infofile, 0o440)
    return infofile

def add_sub(data_dir, subjpre, live=False):
    """Add BIDS sub- prefix to subjects converted with heudiconv"""
    if not subjpre:
        sys.exit('Specify subject prefix')
    subjs = sorted([x for x in os.listdir(data_dir) if subjpre in x 
                                            and 'sub-' not in x])
    for subj in subjs:
        old = op(data_dir, subj)
        new = op(data_dir, 'sub-' + subj)
        logging.info(msg.format(old, new))
        if live:
            os.rename(old, new)

def drop_underscore(data_dir, live=False):
    """ Change directories first, then files """
    subjs = sorted([x for x in os.listdir(data_dir) if x.startswith('sub-')])
    for subj in subjs:
        if subj.count('_') == 0:
            continue
        corr = subj.replace('_', '')
        logging.info(msg.format(op(data_dir, subj), op(data_dir, corr)))
        if not live:
            return
        os.rename(op(data_dir, subj), op(data_dir, corr))
        # refresh after each rename
        layout = BIDSLayout(data_dir)
        files = [f.filename for f in layout.get() if subj in f.filename]
        for file in files:
            fix = file.replace(subj, corr)
            os.rename(file, fix)
                    
def write_scantsv(bids_dir, dicom_dir=None, live=False):
    """ Can be improved with metadata """
    if not os.path.exists(dicom_dir):
        logging.warning('Specify valid dicom directory to write scan.tsvs')
        return
    layout = BIDSLayout(bids_dir)
    subs = sorted([x for x in layout.get_subjects()])
    for sid in subs:
        dcm = read_file(glob(op(dicom_dir, '*' + sid, '*'))[-1], force=True).AcquisitionDate
        date = '-'.join([dcm[:4],dcm[4:6],dcm[6:]])
        logging.info("{0}'s scan date: {1}").format(sid, date)
        scans = []
        for scan in [f.filename for f in layout.get(subject=sid,
                                        extensions=['nii','nii.gz'])]:
            paths = scan.split(os.sep)
            scans.append(os.sep.join(paths[-2:]))
            outname = op(bids_dir, paths[-3], paths[-3] + '_scans.tsv')
        if live:
            with open(outname, 'wt') as tsvfile:
                writer = csv.writer(tsvfile, delimiter='\t')
                writer.writerow(['filename', 'acq_time'])
                for scan in sorted(scans):
                    writer.writerow([scan, date])
            logging.info('Wrote {0}'.format(outname))

def add_taskname(layout, live=False):
    """ Add 'TaskName' key to meta info for each functional task """
    tasks = layout.get_tasks()
    for task in tasks:
        fls = [f.filename for f in layout.get(task=task, ext='.json')]
        for meta in fls:
            add = {'TaskName': task}
            logging.info('Adding {0} to {1}').format(task, meta)
            if live:
                # add to metadata
                add_metadata(meta, add)
    return layout
                    
def fix_fieldmaps(layout, live=False):
    """ Add 'IntendedFor' and 'TotalReadoutTime' keys to meta info
    for each fieldmap -- IN TESTING """
    fmaps = [f.filename for f in layout.get(ext='.json', type='epi')]
    bn = lambda x: os.path.basename(x)
    for fmap in fmaps:
        logging.info('Fieldmap: ' + bn(fmap).split('.json')[0])
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
        rel_niftis = [nif.split('{0}{1}'.format(subj,os.sep))[-1] for nif in niftis]
        # Add intended to all functionals
        readout = calc_readout(load_json(fmap))
        #return meta.keys()
        add = {'IntendedFor': rel_niftis,
               'TotalReadoutTime': readout}
        logging.info('Adding:\n --- ' + '\n --- '.join(rel_niftis))
        if live:
            # add to metadata
            add_metadata(fmap, add)
    return

def calc_readout(meta):
    """Calculate readout time from metadata
    Parameters
    ----------
    meta - dict (json from dcm2niix)
    Returns
    ----------
    readout - float"""
    return ((meta['dcmmeta_shape'][0] - 1) \
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
    parser.add_argument('-p', dest='pre', type=str, 
    					help='''identifier across all subjects''')
    parser.add_argument('-d', '--dicoms', type=str, default=None, 
                        help="""dicom directory""")
    parser.add_argument('--live', default=False, action='store_true',
                        help="""WARNING: DON'T INCLUDE ON FIRST PASS""")
    parser.add_argument('--full', action='store_true', default=False,
                        help="""Run through each option""")
    parser.add_argument('-v', '--verbose', action='store_true', default=False,
                        help="""Make the python logger loud""")
    args = parser.parse_args()
    bids_dir = os.path.abspath(args.datadir)
    if not os.path.exists(bids_dir):
        sys.exit('Specify valid BIDS data directory')
    if args.dicoms:
        dicom_dir = os.path.abspath(args.dicoms)
    else:
        dicom_dir = None
    
    if args.verbose:
        loglevel = logging.DEBUG
    else:
        loglevel = logging.WARNING
    # Set logging output
	logging.basicConfig(filename=op(os.getcwd(), 'mbOUT.txt'),
                        format='%(asctime)s %(levelname)s:%(message)s',
						level=loglevel)
    
    def refresh(bids_dir=bids_dir):
        """ for when files are renamed """
        return BIDSLayout(bids_dir)

    if args.full:
        add_sub(bids_dir, args.pre, args.live)
        drop_underscore(bids_dir, args.live)
        # using BIDS grabbids after renaming files
        if dicom_dir:
        	write_scantsv(bids_dir, dicom_dir, args.live)
        # set layout once no more file renamings
        add_taskname(refresh(), args.live)
        fix_fieldmaps(refresh(), args.live)
    else:
        choice = int(raw_input(OPTIONS))
        if choice == 1:
            add_sub(bids_dir, args.pre, args.live)
        elif choice == 2:
            drop_underscore(bids_dir, args.live)
        elif choice == 3:
            write_scantsv(bids_dir, dicom_dir, args.live)
        elif choice == 4:
            add_taskname(refresh(), args.live)
        elif choice == 5:
            fix_fieldmaps(refresh(), args.live)
        else:
            sys.exit('Option not recognized')
        
if __name__ == '__main__':
    main()
