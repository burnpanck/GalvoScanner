
# This file is autogenerated

import ctypes

from ..base import _handle_errors, tdclib
from ..base import *

tdclib.TDC_enableHbt.restype = ctypes.c_int32
tdclib.TDC_enableHbt.argtypes = [ctypes.c_int32]
def enableHbt(enable):
    _handle_errors(tdclib.TDC_enableHbt(enable),tdclib.TDC_enableHbt,"TDC_enableHbt",(enable))
        
tdclib.TDC_setHbtParams.restype = ctypes.c_int32
tdclib.TDC_setHbtParams.argtypes = [ctypes.c_int32, ctypes.c_int32]
def setHbtParams(binWidth, binCount):
    _handle_errors(tdclib.TDC_setHbtParams(binWidth, binCount),tdclib.TDC_setHbtParams,"TDC_setHbtParams",(binWidth, binCount))
        
tdclib.TDC_setHbtDetectorParams.restype = ctypes.c_int32
tdclib.TDC_setHbtDetectorParams.argtypes = [ctypes.c_double]
def setHbtDetectorParams(jitter):
    _handle_errors(tdclib.TDC_setHbtDetectorParams(jitter),tdclib.TDC_setHbtDetectorParams,"TDC_setHbtDetectorParams",(jitter))
        
tdclib.TDC_setHbtInput.restype = ctypes.c_int32
tdclib.TDC_setHbtInput.argtypes = [ctypes.c_int32, ctypes.c_int32]
def setHbtInput(channel1, channel2):
    _handle_errors(tdclib.TDC_setHbtInput(channel1, channel2),tdclib.TDC_setHbtInput,"TDC_setHbtInput",(channel1, channel2))
        
tdclib.TDC_switchHbtInternalApds.restype = ctypes.c_int32
tdclib.TDC_switchHbtInternalApds.argtypes = [ctypes.c_int32]
def switchHbtInternalApds(internal):
    _handle_errors(tdclib.TDC_switchHbtInternalApds(internal),tdclib.TDC_switchHbtInternalApds,"TDC_switchHbtInternalApds",(internal))
        
tdclib.TDC_resetHbtCorrelations.restype = ctypes.c_int32
tdclib.TDC_resetHbtCorrelations.argtypes = []
def resetHbtCorrelations():
    _handle_errors(tdclib.TDC_resetHbtCorrelations(),tdclib.TDC_resetHbtCorrelations,"TDC_resetHbtCorrelations",())
        
tdclib.TDC_getHbtEventCount.restype = ctypes.c_int32
tdclib.TDC_getHbtEventCount.argtypes = [ctypes.POINTER(ctypes.c_int64), ctypes.POINTER(ctypes.c_int64), ctypes.POINTER(ctypes.c_double)]
def getHbtEventCount(totalCount, lastCount, lastRate):
    _handle_errors(tdclib.TDC_getHbtEventCount(totalCount, lastCount, lastRate),tdclib.TDC_getHbtEventCount,"TDC_getHbtEventCount",(totalCount, lastCount, lastRate))
        
tdclib.TDC_getHbtIntegrationTime.restype = ctypes.c_int32
tdclib.TDC_getHbtIntegrationTime.argtypes = [ctypes.POINTER(ctypes.c_double)]
def getHbtIntegrationTime(intTime):
    _handle_errors(tdclib.TDC_getHbtIntegrationTime(intTime),tdclib.TDC_getHbtIntegrationTime,"TDC_getHbtIntegrationTime",(intTime))
        
tdclib.TDC_getHbtCorrelations.restype = ctypes.c_int32
tdclib.TDC_getHbtCorrelations.argtypes = [ctypes.c_int32, ctypes.POINTER(HbtFunction)]
def getHbtCorrelations(forward, fct):
    _handle_errors(tdclib.TDC_getHbtCorrelations(forward, fct),tdclib.TDC_getHbtCorrelations,"TDC_getHbtCorrelations",(forward, fct))
        
tdclib.TDC_calcHbtG2.restype = ctypes.c_int32
tdclib.TDC_calcHbtG2.argtypes = [ctypes.POINTER(HbtFunction)]
def calcHbtG2(fct):
    _handle_errors(tdclib.TDC_calcHbtG2(fct),tdclib.TDC_calcHbtG2,"TDC_calcHbtG2",(fct))
        
tdclib.TDC_fitHbtG2.restype = ctypes.c_int32
tdclib.TDC_fitHbtG2.argtypes = [ctypes.POINTER(HbtFunction), FctType, ctypes.POINTER(ctypes.c_double), ctypes.POINTER(ctypes.c_double), ctypes.POINTER(ctypes.c_int32)]
def fitHbtG2(fct, fitType, startParams, fitParams, iterations):
    _handle_errors(tdclib.TDC_fitHbtG2(fct, fitType, startParams, fitParams, iterations),tdclib.TDC_fitHbtG2,"TDC_fitHbtG2",(fct, fitType, startParams, fitParams, iterations))
        
tdclib.TDC_getHbtFitStartParams.restype = ctypes.POINTER(ctypes.c_double)
tdclib.TDC_getHbtFitStartParams.argtypes = [FctType]
def getHbtFitStartParams(fctType):
    return tdclib.TDC_getHbtFitStartParams(fctType)
        
tdclib.TDC_calcHbtModelFct.restype = ctypes.c_int32
tdclib.TDC_calcHbtModelFct.argtypes = [FctType, ctypes.POINTER(ctypes.c_double), ctypes.POINTER(HbtFunction)]
def calcHbtModelFct(fctType, params, fct):
    _handle_errors(tdclib.TDC_calcHbtModelFct(fctType, params, fct),tdclib.TDC_calcHbtModelFct,"TDC_calcHbtModelFct",(fctType, params, fct))
        
tdclib.TDC_generateHbtDemo.restype = ctypes.c_int32
tdclib.TDC_generateHbtDemo.argtypes = [FctType, ctypes.POINTER(ctypes.c_double), ctypes.c_double]
def generateHbtDemo(fctType, params, noiseLv):
    _handle_errors(tdclib.TDC_generateHbtDemo(fctType, params, noiseLv),tdclib.TDC_generateHbtDemo,"TDC_generateHbtDemo",(fctType, params, noiseLv))
        
tdclib.TDC_createHbtFunction.restype = ctypes.POINTER(HbtFunction)
tdclib.TDC_createHbtFunction.argtypes = []
def createHbtFunction():
    return tdclib.TDC_createHbtFunction()
        
tdclib.TDC_releaseHbtFunction.restype = None
tdclib.TDC_releaseHbtFunction.argtypes = [ctypes.POINTER(HbtFunction)]
def releaseHbtFunction(fct):
    tdclib.TDC_releaseHbtFunction(fct)
        