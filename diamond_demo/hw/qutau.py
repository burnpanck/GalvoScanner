from ctypes import *
import ctypes
import os.path

import numpy as np

from yde.lib.misc.basics import ExportHelper
from yde.lib.inspect import fake_module
from yde.lib.ctypes_helper import FunctionDeclHelp, EnumMeta
from yde.lib.ctypes_pycp import parse_header, MakeCtype, SimplifyTypeDecl

__all__,export = ExportHelper.make()

#tdcbase = ctypes.windll.tdcbase

_headers_path = os.path.abspath(os.path.join(os.path.dirname(__file__),'TDC_headers'))

#######################################################
# tdcdecl.h
#######################################################

ErrorCode = EnumMeta.from_defstr("ErrorCode","""
#define TDC_Ok               0     /**< Success */
#define TDC_Error          (-1)    /**< Unspecified error */
#define TDC_Timeout          1     /**< Receive timed out */
#define TDC_NotConnected     2     /**< No connection was established */
#define TDC_DriverError      3     /**< Error accessing the USB driver */
#define TDC_DeviceLocked     7     /**< Can't connect device because already in use */
#define TDC_Unknown          8     /**< Unknown error */
#define TDC_NoDevice         9     /**< Invalid device number used in call */
#define TDC_OutOfRange      10     /**< Parameter in function call is out of range */
#define TDC_CantOpen        11     /**< Failed to open specified file */
#define TDC_NotInitialized  12     /**< Library has not been initialized */
#define TDC_NotEnabled      13     /**< Requested Feature is not enabled */
#define TDC_NotAvailable    14     /**< Requested Feature is not available */
""",'TDC_',using_defines=True)

@export
class TDCError(RuntimeError):
    def __init__(self,function,error_code,description=None):
        self.function = str(function)
        self.error_code = error_code
        try:
            name = error_code.name
        except KeyError:
            name = '???'
        try:
            info = error_code.description
        except KeyError:
            info = '???'
        self.description = '%s (%s)'%(
            name,
            info,
        ) + ((': '+description) if description is not None else '')
        self.args = (function,error_code,description)

    def __str__(self):
        return 'While calling %s, the following error was reported:\n%s'%(
            self.function, self.description
        )


_type_interp = MakeCtype(dict(
    Int8 = ctypes.c_int8,
    Int32 = ctypes.c_int32,
    Int64 = ctypes.c_int64,
    Bln32 = ctypes.c_int32,
),stdc_types=True)

#######################################################
# tdcbase.h
#######################################################

# constants
INPUT_CHANNELS = 8
COINC_CHANNELS = 19

# enums
DevType = EnumMeta.from_defstr('DevType',"""
  DEVTYPE_1A,                    /**< Type 1a - no signal conditioning */
  DEVTYPE_1B,                    /**< Type 1b - 8 channel signal conditioning */
  DEVTYPE_1C,                    /**< Type 1c - 3 channel signal conditioning */
  DEVTYPE_NONE                   /**< No device / invalid */
""",'DEVTYPE_')
FileFormat = EnumMeta.from_defstr('FileFormat',"""
  FORMAT_ASCII,                  /**< ASCII format */
  FORMAT_BINARY,                 /**< Uncompressed binary format */
  FORMAT_COMPRESSED,             /**< Compressed binary format */
  FORMAT_NONE                    /**< No format / invalid */
""",'FORMAT_')
SignalCond = EnumMeta.from_defstr('SignalCond',"""
  SCOND_TTL,                     /**< For TTL level signals: Conditioning off */
  SCOND_LVTTL,                   /**< For LVTTL signals:
                                      Trigger at 2V rising edge, termination optional */
  SCOND_NIM,                     /**< For NIM signals:
                                      Trigger at -0.6V falling edge, termination fixed on */
  SCOND_MISC,                    /**< Other signal type: Conditioning on, everything optional */
  SCOND_NONE                     /**< No signal / invalid */
""",'SCOND_')
SimType = EnumMeta.from_defstr('SimType',"""
  SIM_FLAT,                      /**< Time diffs and channel numbers uniformly distributed.
                                      Requires 2 parameters: center, width for time diffs
                                      in TDC units. */
  SIM_NORMAL,                    /**< Time diffs normally distributed, channels uniformly.
                                      Requires 2 parameters: center, width for time diffs
                                      int TDC units. */
  SIM_NONE                       /**< No type / invalid */
""",'SIM_')

# functions

def _handle_errors(ret,fun,funname,args):
    if ret == ErrorCode.Ok:
        return
    try:
        msg = tdcbase.perror(ret)
    except Exception:
        ex = TDCError(funname,ret)
        ex.__suppress_context__ = True   # this exception here is no context
        raise ex
    else:
        raise TDCError(funname,ret,msg)


_type_interp.types.update(
    TDC_DevType = DevType,
    TDC_FileFormat = FileFormat,
    TDC_SignalCond = SignalCond,
    TDC_SimType = SimType,
)
types, statics, functions = parse_header(
    os.path.join(_headers_path,'tdcbase.h'),
    type_interpreter=_type_interp.visit,
)

_ = FunctionDeclHelp(
    tdcbase,
    'TDC_',
    ErrorCode,
    _handle_errors,
    signature_provider = lambda name: [t for a,t in functions.pop(name)[1:]]
)

@_.wrap
def setChannelDelays(wrapped,delays):
    delays = np.array(delays,'i4')
    assert delays.shape==(8,)
    wrapped(delays.ctypes.data_as(ctypes.POINTER(ctypes.c_int32)))

@_.wrap
def getDeviceParams(wrapped):
    channelMask = ctypes.c_int32()
    coincWin = ctypes.c_int32()
    expTime = ctypes.c_int32()
    wrapped(ctypes.byref(channelMask),ctypes.byref(coincWin),ctypes,byref(expTime))
    return channelMask.value, coincWin.value, expTime.value

@_.wrap
def getCoincCounters(wrapped):
    data = np.empty(COINC_CHANNELS,'i4')
    updates = ctypes.c_int32()
    wrapped(data.ctypes.data_as(ctypes.POINTER(ctypes.c_int32)),ctypes.byref(updates))
    return data, updates.value

wrapper_src = ""
no_error_return = set("""
getVersion perror getTimebase getDevType checkFeatureHbt checkFeatureLifeTime
""".split())
for name,v in functions.items():
    assert name.startswith('TDC_')
    shortname = name[4:]
    if False:
        fun = getattr(tdcbase, name)
    else:
        fun = None
#    fun.argtypes = [t for a,t in v[1:]]
    if shortname in no_error_return:
        wrapper_src += """
def {name}({args}):
    return tdcbase.TDC_{name}({args})
        """.format(name=shortname,args=', '.join(a for a,t in v[1:]))
#        fun.restype = v[0][1]
    else:
        wrapper_src += """
def {name}({args}):
    _handle_errors(tdcbase.TDC_{name}({args}))
        """.format(name=shortname,args=', '.join(a for a,t in v[1:]))
#        fun.restype = ErrorCode
del name,shortname,v,types,statics,functions,fun
fake_module(wrapper_src,globals(),locals(),pfx='qutau.tdcbase')
del wrapper_src

#######################################################
# tdcstartstop.h
#######################################################

CROSS_CHANNELS = 8

@_.declare(ctypes.c_int32)
def enableStartStop(enable):
    pass

@_.declare(ctypes.c_int32, ctypes.c_int32)
def setHistogramParams(binWidth, binCount):
    pass

@_.wrap(ctypes.c_int32_p, ctypes.c_int32_p)
def getHistogramParams(wrapped):
    binWidth = ctypes.c_int32()
    binCount = ctypes.c_int32()
    wrapped(ctypes.byref(binWidth), ctypes.byref(binCount))
    return binWidth, binCount

@_.declare()
def clearAllHistograms():
    pass

@_.wrap(
    ctypes.c_int32, ctypes.c_int32,
    ctypes.c_int32,
    ctypes.c_int32_p, ctypes.c_int32_p,
    ctypes.c_int32_p, ctypes.c_int32_p,
    ctypes.c_int32_p, ctypes.c_int32_p,
    ctypes.c_int64_p
)
def getHistogram(wrapped, chanA, chanB, reset):
    raise NotImplementedError

#########################################################################################################
# tdchbt.h
#########################################################################################################

PARAM_SIZE = 5

# function struct
class HbtFunction(ctypes.Structure):
    _fields_ = [
        ("capacity", ctypes.c_int32),
        ("size", ctypes.c_int32),
        ("binWidth", ctypes.c_int32),
        ("indexOffset", ctypes.c_int32),
        ("_values", ctypes.c_double * 0)
    ]

    @property
    def values(self):
        addr = ctypes.cast(self._values, ctypes.POINTER(ctypes.c_double))
        return np.ctypeslib.as_array(addr, self.capacity)

# Enum
FctType = EnumMeta.from_defstr("""
  FCTTYPE_NONE,          /**< No function, invalid.
                              No Parameters. */
  FCTTYPE_COHERENT,      /**< Coherent light.
                              No Parameters. */
  FCTTYPE_THERMAL,       /**< Thermal light source.
                              The function requires 3 parameters: A, c, B */
  FCTTYPE_SINGLE,        /**< Single photon light source.
                              The function requires 1 parameter:
                              t<sub>1</sub> */
  FCTTYPE_ANTIBUNCH,     /**< Three level system light source.
                              The function requires 4 parameters:
                              p<sub>f</sub><sup>2</sup>, c, t<sub>b</sub>, t<sub>a</sub> */
  FCTTYPE_THERM_JIT,     /**< Thermal with detector jitter considered.
                              The function requires 3 parameters: A, c, B */
  FCTTYPE_SINGLE_JIT,    /**< Single photon with detector jitter considered.
                              The function requires 1 parameter:
                              t<sub>1</sub> */
  FCTTYPE_ANTIB_JIT,     /**< Three level system with detector jitter.
                              The function requires 4 parameters:
                              p<sub>f</sub><sup>2</sup>, c, t<sub>b</sub>, t<sub>a</sub> */
  FCTTYPE_THERMAL_OFS,   /**< Thermal with addtitional fit of detector offset
                              The function requires 4 parameters: A, c, B, dt */
  FCTTYPE_SINGLE_OFS,    /**< Single photon with addtitional fit of detector offset
                              The function requires 2 parameters:
                              t<sub>1</sub>, dt */
  FCTTYPE_ANTIB_OFS,     /**< Three level system with addtitional fit of detector offset
                              The function requires 5 parameters:
                              p<sub>f</sub><sup>2</sup>, c, t<sub>b</sub>, t<sub>a</sub>, dt */
  FCTTYPE_THERM_JIT_OFS, /**< Thermal with detector jitter considered and offset fit
                              The function requires 4 parameters: A, c, B, dt */
  FCTTYPE_SINGLE_JIT_OFS,/**< Single photon with detector jitter considered and offset fit
                              The function requires 2 parameters:
                              t<sub>1</sub>, dt */
  FCTTYPE_ANTIB_JIT_OFS  /**< Three level system with detector jitter considered and offset fit
                              The function requires 5 parameters:
                              p<sub>f</sub><sup>2</sup>, c, t<sub>b</sub>, t<sub>a</sub>, dt */
""",'FCTTYPE_')


_type_interp.types.update(
    TDC_HbtFunction = HbtFunction,
    TDC_FctType = FctType,
)
types, statics, functions = parse_header(
    os.path.join(_headers_path,'tdchbt.h'),
    type_interpreter=_type_interp.visit,
)

wrapper_src = ""
no_error_return = set("""
getHbtFitStartParams createHbtFunction
""".split())
for name,v in functions.items():
    assert name.startswith('TDC_')
    shortname = name[4:]
    if False:
        fun = getattr(tdcbase, name)
    else:
        fun = None
    fun.argtypes = [t for a,t in v[1:]]
    if shortname in no_error_return:
        wrapper_src += """
def {name}({args}):
    return tdcbase.TDC_{name}({args})
        """.format(name=shortname,args=', '.join(a for a,t in v[1:]))
        fun.restype = v[0][1]
    else:
        wrapper_src += """
def {name}({args}):
    _handle_errors(tdcbase.TDC_{name}({args}))
        """.format(name=shortname,args=', '.join(a for a,t in v[1:]))
        fun.restype = ErrorCode
del name,shortname,v,types,statics,functions,fun
fake_module(wrapper_src,globals(),locals(),pfx='qutau.tdchbt')
del wrapper_src

################################################################################################################################################
# tdclifetm.h
##########################################################################################################################################

