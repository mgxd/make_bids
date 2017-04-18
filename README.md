# makebids

[![CircleCI](https://circleci.com/gh/mgxd/makebids/tree/master.svg?style=svg)](https://circleci.com/gh/mgxd/makebids/tree/master)
  
Facilitate transition into [BIDS](http://bids.neuroimaging.io) data structure

### Prereq
Converted dicoms with [HeuDiConv](https://github.com/nipy/heudiconv)

### Installation
```
pip install https://github.com/mgxd/makebids/archive/master.zip --process-dependency-links
```
### Note: most of this package has migrated into HeuDiConv.
- `IntendedFor` still useful but makes assumptions based off filename, not `PhaseEncodingDirection` in meta
