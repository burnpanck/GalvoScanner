__author__ = 'yves'

import sys
import os.path

basedir = os.path.abspath(os.path.dirname(__file__))
path = os.path.abspath(os.path.join(basedir,'..','..','github','ydecode','python'))
if path not in sys.path:
    sys.path.append(path)

from yde.lib import ctypes_pycp
ctypes_pycp.default_cpp_path = r'C:\Program Files\LLVM\bin\clang.exe'
ctypes_pycp.extra_cpp_args += '-E -v'.split()
    
from diamond_demo.ScanGui import ScanGui


if __name__ == '__main__':
    ScanGui.main(
#        config_file = os.path.join(basedir,'configs','scanner_config.cfg'),
    )