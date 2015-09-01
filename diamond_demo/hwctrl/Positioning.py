__author__ = 'yves'

import time

import numpy as np
import quantities as pq
import traits.api as tr
import matplotlib.pyplot as plt

from yde.lib.quantity_traits import QuantityTrait, QuantityArrayTrait


# Helper class for storing Lens informatios and to calculate the focal length corresponding to the NA
class Lens:
    def __init__(self, NA, n):
        self.NA = NA
        self.n = n

    def LensNumber(self):
        return 1 / np.tan(np.arcsin(self.NA / self.n))


class Positioning(tr.HasStrictTraits):
    """ Controls a two-axis galvo scanner for x/y positioning and a piezo for focus.
    """
    sensitivity = QuantityArrayTrait([90,90]*pq.V/np.pi,desc="galvo sensitivity V/rad (theta,phi)")
    voltage = QuantityArrayTrait(pq.V,shape=(2,),desc='voltage applied to galvo (theta,phi)')
    angle = tr.Property(
        tr.Array(shape=(2,)),
        fget = lambda self: (self.voltage/self.sensitivity).as_num,
        fset = lambda self, angle: self.set(voltage=angle*self.sensitivity),
        desc = 'galvo deflection angle in radians (theta,phi)',
    )
    position = tr.Property(
        QuantityArrayTrait(pq.um,shape=(2,)),
        fget = lambda self: np.tan(self.angle)*self.focal_plane,
        fset = lambda self, position: self.set(angle = np.arctan((position/self.focal_plane).as_num)),
    )
    lens = tr.Instance(Lens, (1.3, 1.5))
    focal_plane = QuantityTrait(1.5*pq.mm)

    _aout = tr.Instance(Task)


    def __aout_default(self):
        aout = Task()
        aout.set_sample_timing_type('OnDemand')
    def init(self):
        # prepare the output channels
        try:
            self.analog_output = Task()
            self.analog_output.CreateAOVoltageChan(",".join([self.devicePhi, self.deviceTheta, self.piezoDevice]), "",
                                                   -10.0, 10.0, DAQmx_Val_Volts, None)
            # self.analog_output.CreateAOVoltageChan(deviceTheta,"",-10.0,10.0,DAQmx_Val_Volts,None)
            self.analog_output.CfgSampClkTiming("", 10000.0, DAQmx_Val_Rising, DAQmx_Val_ContSamps, 100)

        except(Exception):
            print("Could not init DaqMX")

    def _voltage_changed(self,value):


    # set Voltage directly
    def setVoltagePhi(voltage):
        data = numpy.zeros((200,), dtype=numpy.float64)
        data[:99] = voltage
        data[99:] = self.currentVoltageTheta
        # set the state of the object
        self.currentVoltagePhi = voltage
        self.currentGalvoPhi = phi

        # write to the output channel
        self.analog_output.WriteAnalogF64(100, False, -1, DAQmx_Val_GroupByChannel, data, None, None)
        self.analog_output.StartTask()
        time.sleep(0.0001)
        self.analog_output.StopTask()

    def setVoltageTheta(voltage):
        data = numpy.zeros((200,), dtype=numpy.float64)
        data[:99] = self.currentVoltagePhi
        data[99:] = voltage

        # set the state of the object
        self.currentVoltageTheta = voltage
        self.currentGalvoTheta = theta

        # write to the output channel
        self.analog_output.WriteAnalogF64(100, False, -1, DAQmx_Val_GroupByChannel, data, None, None)
        self.analog_output.StartTask()
        # time.sleep(0.0001)
        self.analog_output.StopTask()

    def calibrate():
        self.calibrationPhi = self.currentVoltagePhi
        self.currentVoltagePhi = 0
        self.calibrationTheta = self.currentVoltageTheta
        self.currentVoltageTheta = 0
        self.currentGalvoTheta = 0
        self.currentGalvoPhi = 0
        self.currentX = 0
        self.currentY = 0


    def setFocus(self, voltage):
        if self.baseVoltage - voltage < 0:
            raise (VoltageCannotBeNegativeException)
        v = self.baseVoltage - voltage
        data = numpy.zeros((300,), dtype=numpy.float64)
        data[:100] = self.currentVoltagePhi
        data[100:200] = self.currentVoltageTheta
        data[200:] = v
        # set the state of the object
        self.currentPiezoVoltage = v

        # write to the output channel
        self.analog_output.WriteAnalogF64(100, False, -1, DAQmx_Val_GroupByChannel, data, None, None)
        self.analog_output.StartTask()

        self.analog_output.StopTask()

    # setAngles for the galvo (enter values in degree), private: use setX and setY for public access
    def __setPhi(self, phi):
        voltage = self.sensitivityDeg * phi + self.calibrationPhi
        data = numpy.zeros((300,), dtype=numpy.float64)
        data[:100] = voltage
        data[100:200] = self.currentVoltageTheta
        data[200:] = self.currentPiezoVoltage
        self.testData = data
        # set the state of the object
        self.currentVoltagePhi = voltage
        self.currentGalvoPhi = phi

        # write to the output channel
        self.analog_output.WriteAnalogF64(100, False, -1, DAQmx_Val_GroupByChannel, data, None, None)
        self.analog_output.StartTask()

        self.analog_output.StopTask()

    def __setPhiRad(self, phiRad):
        self.__setPhi(180. / numpy.pi * phiRad)

    def __setTheta(self, theta):
        voltage = self.sensitivityDeg * theta + self.calibrationTheta
        data = numpy.zeros((300,), dtype=numpy.float64)
        data[:100] = self.currentVoltagePhi
        data[100:200] = voltage
        data[200:] = self.currentPiezoVoltage
        self.testData = data
        # set the state of the object
        self.currentVoltageTheta = voltage
        self.currentGalvoTheta = theta

        # write to the output channel
        self.analog_output.WriteAnalogF64(100, False, -1, DAQmx_Val_GroupByChannel, data, None, None)
        self.analog_output.StartTask()
        # time.sleep(0.0001)
        self.analog_output.StopTask()

    def __setThetaRad(self, thetaRad):
        self.__setTheta(180. / numpy.pi * thetaRad)

    # get state of galvo -> return angle in degree
    def getAnglePhiDegree(self):
        return self.currentGalvoPhi * (180. / numpy.pi)

    def getAngleThetaDegree(self):
        return self.currentGalvoTheta * (180. / numpy.pi)