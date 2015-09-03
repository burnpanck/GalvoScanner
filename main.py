__author__ = 'yves'

import sys
import os.path

basedir = os.path.abspath(os.path.dirname(__file__))
path = os.path.abspath(os.path.join(basedir,'..','..','github','ydecode','python'))
if path not in sys.path:
    sys.path.append(path)

from diamond_demo.ScanGui import ScanGui


if __name__ == '__main__':
    ScanGui.main(
#        config_file = os.path.join(basedir,'configs','scanner_config.cfg'),
    )