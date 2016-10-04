__author__ = 'yves'

import os.path

from .base import *

_headers_path = os.path.abspath(os.path.join(os.path.dirname(__file__),'TDC_headers'))
if not all(os.path.exists(os.path.join(_headers_path,'tdc'+n+'.py')) for n in 'base hbt'.split()):
    from . import _make_wrappers

if tdclib is not None:
    from .TDC_headers.tdcbase import *
    from .TDC_headers.tdchbt import *
