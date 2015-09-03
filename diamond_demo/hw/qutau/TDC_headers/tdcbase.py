
# This file is autogenerated

import ctypes

from ..base import _handle_errors, tdclib
from ..base import *

tdclib.TDC_setChannelDelays.restype = ctypes.c_int32
tdclib.TDC_setChannelDelays.argtypes = [ctypes.POINTER(ctypes.c_int32)]
def setChannelDelays(delays):
    delays = np.array(delays,'i4')
    assert delays.shape==(8,)
    _handle_errors(tdclib.TDC_setChannelDelays(delays.ctypes.data_as(ctypes.POINTER(ctypes.c_int32))),tdclib.TDC_setChannelDelays,"TDC_setChannelDelays",(delays))
        
tdclib.TDC_getDeviceParams.restype = ctypes.c_int32
tdclib.TDC_getDeviceParams.argtypes = [ctypes.POINTER(ctypes.c_int32), ctypes.POINTER(ctypes.c_int32), ctypes.POINTER(ctypes.c_int32)]
def getDeviceParams():
    channelMask = ctypes.c_int32()
    coincWin = ctypes.c_int32()
    expTime = ctypes.c_int32()
    _handle_errors(tdclib.TDC_getDeviceParams(ctypes.byref(channelMask),ctypes.byref(coincWin),ctypes,byref(expTime)),tdclib.TDC_getDeviceParams,"TDC_getDeviceParams",())
    return channelMask.value, coincWin.value, expTime.value
        
tdclib.TDC_getCoincCounters.restype = ctypes.c_int32
tdclib.TDC_getCoincCounters.argtypes = [ctypes.POINTER(ctypes.c_int32), ctypes.POINTER(ctypes.c_int32)]
def getCoincCounters():
    data = np.empty(COINC_CHANNELS,'i4')
    updates = ctypes.c_int32()
    _handle_errors(tdclib.TDC_getCoincCounters(data.ctypes.data_as(ctypes.POINTER(ctypes.c_int32)),ctypes.byref(updates)),tdclib.TDC_getCoincCounters,"TDC_getCoincCounters",())
    return data, updates.value
        
tdclib.TDC_getVersion.restype = ctypes.c_double
tdclib.TDC_getVersion.argtypes = []
def getVersion():
    return tdclib.TDC_getVersion()
        
tdclib.TDC_perror.restype = ctypes.POINTER(c_char)
tdclib.TDC_perror.argtypes = [ctypes.c_int32]
def perror(rc):
    return tdclib.TDC_perror(rc)
        
tdclib.TDC_getTimebase.restype = ctypes.c_double
tdclib.TDC_getTimebase.argtypes = []
def getTimebase():
    return tdclib.TDC_getTimebase()
        
tdclib.TDC_init.restype = ctypes.c_int32
tdclib.TDC_init.argtypes = [ctypes.c_int32]
def init(deviceId):
    _handle_errors(tdclib.TDC_init(deviceId),tdclib.TDC_init,"TDC_init",(deviceId))
        
tdclib.TDC_deInit.restype = ctypes.c_int32
tdclib.TDC_deInit.argtypes = []
def deInit():
    _handle_errors(tdclib.TDC_deInit(),tdclib.TDC_deInit,"TDC_deInit",())
        
tdclib.TDC_getDevType.restype = DevType
tdclib.TDC_getDevType.argtypes = []
def getDevType():
    return tdclib.TDC_getDevType()
        
tdclib.TDC_checkFeatureHbt.restype = ctypes.c_int32
tdclib.TDC_checkFeatureHbt.argtypes = []
def checkFeatureHbt():
    return tdclib.TDC_checkFeatureHbt()
        
tdclib.TDC_checkFeatureLifeTime.restype = ctypes.c_int32
tdclib.TDC_checkFeatureLifeTime.argtypes = []
def checkFeatureLifeTime():
    return tdclib.TDC_checkFeatureLifeTime()
        
tdclib.TDC_configureSignalConditioning.restype = ctypes.c_int32
tdclib.TDC_configureSignalConditioning.argtypes = [ctypes.c_int32, SignalCond, ctypes.c_int32, ctypes.c_int32, ctypes.c_double]
def configureSignalConditioning(channel, conditioning, edge, term, threshold):
    _handle_errors(tdclib.TDC_configureSignalConditioning(channel, conditioning, edge, term, threshold),tdclib.TDC_configureSignalConditioning,"TDC_configureSignalConditioning",(channel, conditioning, edge, term, threshold))
        
tdclib.TDC_configureSyncDivider.restype = ctypes.c_int32
tdclib.TDC_configureSyncDivider.argtypes = [ctypes.c_int32, ctypes.c_int32]
def configureSyncDivider(divider, reconstruct):
    _handle_errors(tdclib.TDC_configureSyncDivider(divider, reconstruct),tdclib.TDC_configureSyncDivider,"TDC_configureSyncDivider",(divider, reconstruct))
        
tdclib.TDC_configureApdCooling.restype = ctypes.c_int32
tdclib.TDC_configureApdCooling.argtypes = [ctypes.c_int32, ctypes.c_int32]
def configureApdCooling(fanSpeed, temp):
    _handle_errors(tdclib.TDC_configureApdCooling(fanSpeed, temp),tdclib.TDC_configureApdCooling,"TDC_configureApdCooling",(fanSpeed, temp))
        
tdclib.TDC_configureInternalApds.restype = ctypes.c_int32
tdclib.TDC_configureInternalApds.argtypes = [ctypes.c_int32, ctypes.c_double, ctypes.c_double]
def configureInternalApds(apd, bias, thrsh):
    _handle_errors(tdclib.TDC_configureInternalApds(apd, bias, thrsh),tdclib.TDC_configureInternalApds,"TDC_configureInternalApds",(apd, bias, thrsh))
        
tdclib.TDC_enableChannels.restype = ctypes.c_int32
tdclib.TDC_enableChannels.argtypes = [ctypes.c_int32]
def enableChannels(channelMask):
    _handle_errors(tdclib.TDC_enableChannels(channelMask),tdclib.TDC_enableChannels,"TDC_enableChannels",(channelMask))
        
tdclib.TDC_setCoincidenceWindow.restype = ctypes.c_int32
tdclib.TDC_setCoincidenceWindow.argtypes = [ctypes.c_int32]
def setCoincidenceWindow(coincWin):
    _handle_errors(tdclib.TDC_setCoincidenceWindow(coincWin),tdclib.TDC_setCoincidenceWindow,"TDC_setCoincidenceWindow",(coincWin))
        
tdclib.TDC_setExposureTime.restype = ctypes.c_int32
tdclib.TDC_setExposureTime.argtypes = [ctypes.c_int32]
def setExposureTime(expTime):
    _handle_errors(tdclib.TDC_setExposureTime(expTime),tdclib.TDC_setExposureTime,"TDC_setExposureTime",(expTime))
        
tdclib.TDC_switchTermination.restype = ctypes.c_int32
tdclib.TDC_switchTermination.argtypes = [ctypes.c_int32]
def switchTermination(on):
    _handle_errors(tdclib.TDC_switchTermination(on),tdclib.TDC_switchTermination,"TDC_switchTermination",(on))
        
tdclib.TDC_configureSelftest.restype = ctypes.c_int32
tdclib.TDC_configureSelftest.argtypes = [ctypes.c_int32, ctypes.c_int32, ctypes.c_int32, ctypes.c_int32]
def configureSelftest(channelMask, period, burstSize, burstDist):
    _handle_errors(tdclib.TDC_configureSelftest(channelMask, period, burstSize, burstDist),tdclib.TDC_configureSelftest,"TDC_configureSelftest",(channelMask, period, burstSize, burstDist))
        
tdclib.TDC_getDataLost.restype = ctypes.c_int32
tdclib.TDC_getDataLost.argtypes = [ctypes.POINTER(ctypes.c_int32)]
def getDataLost(lost):
    _handle_errors(tdclib.TDC_getDataLost(lost),tdclib.TDC_getDataLost,"TDC_getDataLost",(lost))
        
tdclib.TDC_setTimestampBufferSize.restype = ctypes.c_int32
tdclib.TDC_setTimestampBufferSize.argtypes = [ctypes.c_int32]
def setTimestampBufferSize(size):
    _handle_errors(tdclib.TDC_setTimestampBufferSize(size),tdclib.TDC_setTimestampBufferSize,"TDC_setTimestampBufferSize",(size))
        
tdclib.TDC_freezeBuffers.restype = ctypes.c_int32
tdclib.TDC_freezeBuffers.argtypes = [ctypes.c_int32]
def freezeBuffers(freeze):
    _handle_errors(tdclib.TDC_freezeBuffers(freeze),tdclib.TDC_freezeBuffers,"TDC_freezeBuffers",(freeze))
        
tdclib.TDC_getLastTimestamps.restype = ctypes.c_int32
tdclib.TDC_getLastTimestamps.argtypes = [ctypes.c_int32, ctypes.POINTER(ctypes.c_int64), ctypes.POINTER(ctypes.c_int8), ctypes.POINTER(ctypes.c_int32)]
def getLastTimestamps(reset, timestamps, channels, valid):
    _handle_errors(tdclib.TDC_getLastTimestamps(reset, timestamps, channels, valid),tdclib.TDC_getLastTimestamps,"TDC_getLastTimestamps",(reset, timestamps, channels, valid))
        
tdclib.TDC_writeTimestamps.restype = ctypes.c_int32
tdclib.TDC_writeTimestamps.argtypes = [ctypes.POINTER(c_char), FileFormat]
def writeTimestamps(filename, format):
    _handle_errors(tdclib.TDC_writeTimestamps(filename, format),tdclib.TDC_writeTimestamps,"TDC_writeTimestamps",(filename, format))
        
tdclib.TDC_inputTimestamps.restype = ctypes.c_int32
tdclib.TDC_inputTimestamps.argtypes = [ctypes.POINTER(ctypes.c_int64), ctypes.POINTER(ctypes.c_int8), ctypes.c_int32]
def inputTimestamps(timestamps, channels, count):
    _handle_errors(tdclib.TDC_inputTimestamps(timestamps, channels, count),tdclib.TDC_inputTimestamps,"TDC_inputTimestamps",(timestamps, channels, count))
        
tdclib.TDC_readTimestamps.restype = ctypes.c_int32
tdclib.TDC_readTimestamps.argtypes = [ctypes.POINTER(c_char), FileFormat]
def readTimestamps(filename, format):
    _handle_errors(tdclib.TDC_readTimestamps(filename, format),tdclib.TDC_readTimestamps,"TDC_readTimestamps",(filename, format))
        
tdclib.TDC_generateTimestamps.restype = ctypes.c_int32
tdclib.TDC_generateTimestamps.argtypes = [SimType, ctypes.POINTER(ctypes.c_double), ctypes.c_int32]
def generateTimestamps(type, par, count):
    _handle_errors(tdclib.TDC_generateTimestamps(type, par, count),tdclib.TDC_generateTimestamps,"TDC_generateTimestamps",(type, par, count))
        