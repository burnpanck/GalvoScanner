__author__ = 'yves'

import time

import numpy as np
import quantities as pq
import traits.api as tr

try:
    import PyDAQmx as DAQmx
except Exception:
    DAQmx = None

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
    sensitivity = QuantityArrayTrait([90,90]*pq.V/np.pi,desc="galvo sensitivity V/rad (phi,theta)")
    galvo_voltage = QuantityArrayTrait(pq.V,shape=(2,),desc='voltage applied to galvo (phi,theta)')
    piezo_voltage = QuantityTrait(pq.V,desc="piezo for focusing")
    galvo_angle = tr.Property(
        handler = tr.Array(shape=(2,)),
        fget = lambda self: (self.galvo_voltage/self.sensitivity).as_num,
        fset = lambda self, angle: self.trait_set(galvo_voltage=angle*self.sensitivity),
        desc = 'galvo deflection angle in radians (phi,theta)',
    )
    position = tr.Property(
        handler = QuantityArrayTrait(pq.um,shape=(2,)),
        fget = lambda self: np.tan(self.galvo_angle)*self.focal_plane,
        fset = lambda self, position: self.trait_set(galvo_angle = np.arctan((position/self.focal_plane).as_num)),
    )
    lens = tr.Instance(Lens, (1.3, 1.5))
    focal_plane = QuantityTrait(1.5*pq.mm)

    _aout = tr.Instance('PyDAQmx.Task')
    _theta_terminal = tr.Str()
    _phi_terminal = tr.Str()
    _focus_terminal = tr.Str()

    def __aout_default(self):
        aout = DAQmx.Task()
        aout.CreateAOVoltageChan(
            ",".join([self._phi_terminal, self._theta_terminal]),
            "",
            -10.0, 10.0,
            DAQmx.DAQmx_Val_Volts, None
        )
        aout.CreateAOVoltageChan(
            self._focus_terminal,
            "",
            0, 5.0,
            DAQmx.DAQmx_Val_Volts, None
        )
        aout.SetSampTimingType(DAQmx.DAQmx_Val_OnDemand)
        aout.StartTask()
        return aout

    def _release_tasks(self):
        aout = self._aout
        aout.StopTask()
        aout.ClearTask()
        self._aout = None

    def _galvo_voltage_changed(self,value):
        V = np.r_[
            value.mag_in(pq.V),
            float(self.piezo_voltage.mag_in(pq.V))
        ]
        self._aout.WriteAnalogF64(1, False, -1, DAQmx.DAQmx_Val_GroupByChannel, V, None, None)

    def _piezo_voltage_changed(self,value):
        V = np.r_[
            self.galvo_voltage.mag_in(pq.V),
            float(value.mag_in(pq.V)),
        ]
        self._aout.WriteAnalogF64(1, False, -1, DAQmx.DAQmx_Val_GroupByChannel, V, None, None)


