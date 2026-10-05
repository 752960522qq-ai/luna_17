#!/usr/bin/env python3
"""Prepare r10 Unity resources and model; does not create an APK."""
import argparse
import json
from pathlib import Path
from tankbuilder.t54_controls import repair_resources

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source',type=Path,required=True)
    p.add_argument('--model',type=Path,required=True)
    p.add_argument('--output-dir',type=Path,required=True)
    a=p.parse_args();r=repair_resources(a.source,a.model,a.output_dir)
    print(json.dumps({k:r[k] for k in ['passed','output_sha256','turret_triangles','hull_triangles']},indent=2))
