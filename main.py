__author__ = 'yves'

import sys
import os.path
import logging

basedir = os.path.abspath(os.path.dirname(__file__))
path = os.path.abspath(os.path.join(basedir,'..','github','ydecode','python'))
if path not in sys.path:
    sys.path.append(path)

from diamond_demo.ScanGuiQt import ScanGui

root_logger = logging.root

def excepthook(exctype, excvalue, tb):
    import traceback
    traceback.print_exception(exctype, excvalue, tb)
    root_logger.exception('Unhandled exception!',exc_info=(exctype, excvalue, tb))
#    sys.exit(-1)

if __name__ == '__main__':
    sys.excepthook = excepthook
    root_logger.level = logging.DEBUG
    ScanGui.main(
        config_file = os.path.join(basedir,'configs','scanner_config.cfg'),
    )