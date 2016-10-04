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
    bin_centres = tr.Property(depends_on='start_delay,bin_size,raw_result')
    integration_time = QuantityTrait(pq.s)
    signal_ratio = tr.CFloat(desc='ratio signal to (signal+background)')
    raw_result = tr.Array(shape=(None,))

    def g2(self,normalise=True,correct=True):
        ret = self.raw_result
        if normalise:
            long_time = (np.sum(ret[:5])+np.sum(ret[-5:]))*0.1
            if long_time>0:
                ret /= long_time

        if correct:
            s2 = self.signal_ratio**2
            s2 = max(s2, 1-ret.min())
            ret = (ret - (1-s2))/s2
        return ret

    @tr.cached_property
    def _get_bin_centres(self):
        return self.start_delay + np.arange(self.raw_result.size)*self.bin_size
        
class RealTDC(RepeatingTaskRunner):
    exposure_time = QuantityTrait(100*pq.ms)
    _timebase = tr.Property(
        QuantityTrait(pq.s)
    )
    enable_HBT = tr.Bool
    freeze = tr.Bool
    _channels = tr.Array(int,shape=(2,),value=np.r_[4,5])
    signal_ratio = tr.CFloat(1,desc='ratio signal to (signal+background)')
    
    _guard = tr.Instance(threading.Condition,())

    new_data = tr.Event

    _hbt_fun = tr.Any

    _last_read = tr.CFloat()
    _min_wait = tr.CFloat(0.005)

    guard = tr.Instance(threading.Condition,factory=lambda:threading.Condition(threading.RLock()))
    max_period = tr.Property(
        fget = lambda self: self.exposure_time.mag_in(pq.s)
    )

    def __init__(self, **kw):
        super(RealTDC,self).__init__(**kw)
        self.reset()

    @tr.cached_property
    def _get__timebase(self):
        with self._guard:
            return qutau.getTimebase()*pq.s

    def one_pass(self, dt):
        from yde.lib.py2to3 import monotonic
        now = monotonic()
        with self._guard:
            buf, nupd = qutau.getCoincCounters()
        lr = self._last_read
        if nupd:
            self._last_read = now
            if nupd>1:
                self.logger.warn('Missed counter updates! (nupd=%d)',nupd)
            self.new_data = buf[self._channels]/self.exposure_time
            
        self.require_update_by(max(
            now + self._min_wait,
            self._last_read + self.exposure_time.mag_in(pq.s)*0.9
        ))
#        print('photon counts ',buf[self._channels],nupd,dt,now-lr,now-self._last_read,self._next_pass-now)

    def _exposure_time_changed(self,value):
        with self._guard:
            qutau.setExposureTime(value.mag_in(pq.ms))
    
    def _enable_HBT_changed(self,value):
        with self._guard:
            qutau.enableHbt(value)

    def _freeze_changed(self,value):
        with self._guard:
            qutau.freezeBuffers(value)

    def startup(self):
        with self._guard:
            # accept any device
            qutau.init(-1)
            # enable all channels
            qutau.enableChannels(int(np.sum(1<<self._channels)))
            # enable start stop
            qutau.enableStartStop(True)
            qutau.clearAllHistograms()
        # enable hbt
        self._enable_HBT_changed(self.enable_HBT)
        # exposure time in ms
        self._exposure_time_changed(self.exposure_time)
        print('started')
    
    def shutdown(self):
        with self._guard:
            if self._hbt_fun is not None:
                qutau.releaseHbtFunction(ctypes.byref(self._hbt_fun))
                self._hbt_fun = None
            qutau.deInit()
    
    def failed(self):
        self.shutdown()
    
    def reset(self):
        self.stop()
        self.start()

    def deinit(self):
        self.stop()

    def setup_hbt(self, reso, range):
        prescale = int(np.round((reso/self._timebase).as_num))
        reso = prescale*self._timebase
        count = int(np.ceil((range/reso).as_num))
        with self._guard:
            qutau.setHbtParams(
                prescale,
                count
            )
            if self._hbt_fun is not None:
                qutau.releaseHbtFunction(ctypes.byref(self._hbt_fun))
            self._hbt_fun = qutau.createHbtFunction()[0]
            qutau.resetHbtCorrelations()

    @property
    def hbt(self):
        fun = self._hbt_fun
        dt = self._timebase*fun.binWidth
        time = ctypes.c_double()
        total_count = ctypes.c_int64()
        last_count = ctypes.c_int64()
        last_rate = ctypes.c_double()
        with self._guard:
            qutau.freezeBuffers(True)
            qutau.calcHbtG2(ctypes.byref(fun))
            qutau.getHbtEventCount(
                ctypes.byref(total_count),
                ctypes.byref(last_count),
                ctypes.byref(last_rate)  # Hz
            )
            qutau.getHbtIntegrationTime(ctypes.byref(time))
            time = time.value
            qutau.freezeBuffers(self.freeze)
        total_count = total_count.value
        last_count = last_count.value
        last_rate = last_rate.value
#        print('hbt ',total_count,last_count,total_count/time,last_rate)
        return HBTResult(
            bin_size = dt,
            start_delay = -fun.indexOffset*dt,
            raw_result = fun.values[:fun.size],
            integration_time = time*pq.s,
            signal_ratio = self.signal_ratio,
        )


class SimulatedTDC(RealTDC):
    _timebase = tr.Disallow
    _channels = tr.Disallow

    _hbt_fun = tr.Disallow

    rate = QuantityTrait(100*pq.kHz)
    _hbt_setup = tr.Any()

    def __init__(self, **kw):
        super(SimulatedTDC, self).__init__(**kw)
        self.reset()

    def one_pass(self, dt):
        from yde.lib.py2to3 import monotonic
        now = monotonic()
        lr = self._last_read
        if now>=lr+self.exposure_time.mag_in(pq.s):
            self._last_read = now
            lam = pq.unitless(self.exposure_time*self.rate)
            self.new_data = np.random.poisson(lam,size=(2,)) / self.exposure_time

        self.require_update_by(max(
            now + self._min_wait,
            self._last_read + self.exposure_time.mag_in(pq.s) * 0.9
        ))

    #        print('photon counts ',buf[self._channels],nupd,dt,now-lr,now-self._last_read,self._next_pass-now)

    def _exposure_time_changed(self, value):
        pass

    def _enable_HBT_changed(self, value):
        pass

    def _freeze_changed(self, value):
        pass

    def startup(self):
        pass

    def shutdown(self):
        pass

    def reset(self):
        self.stop()
        self.start()

    def deinit(self):
        self.stop()

    def setup_hbt(self, reso, range):
        n = int(np.round(pq.unitless(range/reso)))
        self._hbt_setup = reso,n

    @property
    def hbt(self):
        reso,n = self._hbt_setup
        return HBTResult(
            bin_size = reso,
            start_delay = -n * reso,
            raw_result = np.zeros(2*n+1,int),
            integration_time = 1 * pq.s,
            signal_ratio = self.signal_ratio,
        )

TDC = RealTDC if qutau.tdclib is not None else SimulatedTDC
