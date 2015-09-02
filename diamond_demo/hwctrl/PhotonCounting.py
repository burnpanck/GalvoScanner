__author__ = 'yves'

import threading
import ctypes
import time

import numpy as np
import quantities as pq
import traits.api as tr

from yde.lib.quantity_traits import QuantityArrayTrait, QuantityTrait
from yde.lib.threading import RepeatingTaskRunner

from ..hw import qutau

class HBTResult(tr.HasStrictTraits):
    start_delay = QuantityTrait(pq.ns)
    bin_size = QuantityTrait(pq.ns)
    bin_centres = tr.Property
    integration_time = QuantityTrait(pq.s)
    background_rates = QuantityArrayTrait(pq.kHz,shape=(2,))
    raw_result = tr.Array(shape=(None,))

    def g2(self,normalise=True,correct=True):
        ret = self.raw_result
        if normalise:
            long_time = (np.sum(ret[:5])+np.sum(ret[-5:]))*0.1
            if long_time>0:
                ret /= long_time

        if correct:
            fg_ratio = self.sigToBack**2
            ret = (ret - (1-fg_ratio))/fg_ratio
        return ret

class TDC(RepeatingTaskRunner):
    exposure_time = QuantityTrait(100*pq.ms)
    _timebase = tr.Property(
        QuantityTrait(pq.s)
    )
    enable_HBT = tr.Bool
    freeze = tr.Bool
    _channels = tr.Array(int,shape=(2,),value=np.r_[4,5])
    background_rates = QuantityArrayTrait(pq.kHz,shape=(None,))
    
    _guard = tr.Instance(threading.Condition,())

    new_data = tr.Event

    _hbt_fun = tr.Instance('TDC.TDC_HbtFunction')

    _last_read = tr.CFloat()
    _min_wait = tr.CFloat(0.005)

    guard = tr.Instance(threading.Condition,factory=lambda:threading.Condition(threading.RLock()))
    max_period = tr.Property(
        fget = lambda self: self.exposure_time.mag_in(pq.s)
    )

    def __init__(self, **kw):
        super(TDC,self).__init__(**kw)
        self.reset()

    @tr.cached_property
    def _get__timebase(self):
        with self._guard:
            return qutau.TDC_getTimebase()*pq.s

    def one_pass(self, dt):
        from yde.lib.py2to3 import monotonic
        buf = np.empty(19,'i4')
        nupd = ctypes.c_int32()
        now = monotonic()
        with self._guard:
            print('get coinc')
            qutau.TDC_getCoincCounters(
                buf.ctypes.data_as(ctypes.POINTER(ctypes.c_int32)),
                ctypes.byref(nupd)
            )
            print('get coinc done')
        nupd = nupd.value
        lr = self._last_read
        if nupd:
            self._last_read = now
            if nupd>1:
                self.logger.warn('Missed counter updates! (nupd=%d)',nupd)
            print('notify counts')
            self.new_data = buf[self._channels]/self.exposure_time
            print('done notify counts')
            
        self.require_update_by(max(
            now + self._min_wait,
            self._last_read + self.exposure_time.mag_in(pq.s)*0.9
        ))
        print('photon counts ',buf[self._channels],nupd,dt,now-lr,now-self._last_read,self._next_pass-now)

    def _exposure_time_changed(self,value):
        with self._guard:
            qutau.TDC_setExposureTime(value.mag_in(pq.ms))
    
    def _enable_HBT_changed(self,value):
        with self._guard:
            qutau.TDC_enableHbt(value)

    def _freeze_changed(self,value):
        with self._guard:
            qutau.TDC_freezeBuffers(value)

    def startup(self):
        with self._guard:
            # accept any device
            qutau.TDC_init(-1)
            # enable all channels
            qutau.TDC_enableChannels(int(np.sum(1<<self._channels)))
            # enable start stop
            qutau.TDC_enableStartStop(True)
            qutau.TDC_clearAllHistograms()
        # enable hbt
        self._enable_HBT_changed(self.enable_HBT)
        # exposure time in ms
        self._exposure_time_changed(self.exposure_time)
    
    def shutdown(self):
        with self._guard:
            print('shutdown')
            if self._hbt_fun is not None:
                qutau.TDC_releaseHbtFunction(ctypes.byref(self._hbt_fun))
                self._hbt_fun = None
            qutau.TDC_deInit()
            print('shutdown done')
    
    def failed(self):
        self.shutdown()
    
    def reset(self):
        self.start()

    def deinit(self):
        self.stop()

    def setup_hbt(self, range, reso=1*pq.ns ):
        prescale = int(round((reso/self._timebase).as_num))
        reso = prescale*self._timebase
        count = int(np.ceil((range/reso).as_num))
        with self._guard:
            qutau.TDC_setHbtParams(
                prescale,
                count
            )
            if self._hbt_fun is not None:
                qutau.TDC_releaseHbtFunction(ctypes.byref(self._hbt_fun))
            self._hbt_fun = qutau.TDC_createHbtFunction()[0]
            qutau.TDC_resetHbtCorrelations()

    @property
    def hbt(self):
        fun = self._hbt_fun
        dt = self._timebase*fun.binWidth
        time = ctypes.c_double()
        total_count = ctypes.c_int64()
        last_count = ctypes.c_int64()
        last_rate = ctypes.c_double()
        with self._guard:
            qutau.TDC_freezeBuffers(True)
            qutau.TDC_calcHbtG2(ctypes.byref(fun))
            qutau.TDC_getHbtEventCount(
                ctypes.byref(total_count),
                ctypes.byref(last_count),
                ctypes.byref(last_rate)  # Hz
            )
            qutau.TDC_getHbtIntegrationTime(ctypes.byref(time))
            time = time.value
            qutau.TDC_freezeBuffers(self.freeze)
        return HBTResult(
            bin_size = dt,
            start_delay = -fun.indexOffset*dt,
            raw_result = fun.values[:fun.size],
            integration_time = time*pq.s,
        )

