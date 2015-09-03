import ctypes
import os.path

import numpy as np

from yde.lib.misc.basics import ExportHelper
from yde.lib.ctypes_helper import FunctionDeclHelp, EnumMeta

__all_inactive__,export = ExportHelper.make()

try:
    tdclib = ctypes.windll.tdcbase
except AttributeError:
    tdclib = None

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


_type_aliases = dict(
    Int8 = ctypes.c_int8,
    Int32 = ctypes.c_int32,
    Int64 = ctypes.c_int64,
    Bln32 = ctypes.c_int32,
)

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
_type_aliases.update(
    TDC_DevType = DevType,
    TDC_FileFormat = FileFormat,
    TDC_SignalCond = SignalCond,
    TDC_SimType = SimType,
)

# functions

def _handle_errors(ret,fun,funname,args):
    ret = ErrorCode(ret)
    if ret == ErrorCode.Ok:
        return
    try:
        msg = ctypes.c_char_p(tdclib.TDC_perror(ret))
    except Exception:
        ex = TDCError(funname,ret,'(arguments: %s)'%str(args))
        ex.__suppress_context__ = True   # this exception here is no context
        raise ex
    else:
        raise TDCError(funname,ret,msg+'(arguments: %s)'%str(args))

_ = FunctionDeclHelp(
    tdclib,
    'TDC_',
    ErrorCode,
    _handle_errors
)

def funfix(staticmethod):
    return staticmethod.__func__
    
#######################################################
# tdcstartstop.h
#######################################################

CROSS_CHANNELS = 8

if tdclib is not None:
    @funfix
    @_.declare(ctypes.c_int32)
    def enableStartStop(enable):
        pass

    @funfix
    @_.declare(ctypes.c_int32, ctypes.c_int32)
    def setHistogramParams(binWidth, binCount):
        pass

    @funfix
    @_.wrap(ctypes.POINTER(ctypes.c_int32), ctypes.POINTER(ctypes.c_int32))
    def getHistogramParams(wrapped):
        binWidth = ctypes.c_int32()
        binCount = ctypes.c_int32()
        wrapped(ctypes.byref(binWidth), ctypes.byref(binCount))
        return binWidth, binCount

    @funfix
    @_.declare()
    def clearAllHistograms():
        pass

    @funfix
    @_.wrap(
        ctypes.c_int32, ctypes.c_int32,
        ctypes.c_int32,
        ctypes.POINTER(ctypes.c_int32), ctypes.POINTER(ctypes.c_int32),
        ctypes.POINTER(ctypes.c_int32), ctypes.POINTER(ctypes.c_int32),
        ctypes.POINTER(ctypes.c_int32), ctypes.POINTER(ctypes.c_int32),
        ctypes.POINTER(ctypes.c_int64)
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
        return np.ctypeslib.as_array(addr, (self.capacity,))

# Enum
FctType = EnumMeta.from_defstr('FctType', """
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


_type_aliases.update(
    TDC_HbtFunction = HbtFunction,
    HBT_FctType = FctType,
)

################################################################################################################################################
# tdclifetm.h
##########################################################################################################################################

