__author__ = 'yves'

import numpy as np
import quantities as pq
import traits.api as tr

from yde.lib.quantity_traits import QuantityTrait, QuantityArrayTrait
from yde.lib.threading import RepeatingTaskRunner

try:
    from yde.labdev.flycap import api
except (ImportError, OSError):
    api = None

_dB2natlog = np.log(10)/10
_natlog2dB = 10/np.log(10)

class RealFlyCam(RepeatingTaskRunner):
    _cam = tr.Any

    connected = tr.Bool(desc='read only')

    shutter = tr.Property(
        QuantityTrait(pq.ms),
    )
    shutter_range = QuantityArrayTrait(pq.ms,shape=(2,))
    gain = tr.Property(
        tr.CFloat(desc='gain factor')
    )
    gain_range = tr.Array(float,shape=(2,))

#    enabled_for = tr.Set(desc="set of ID's used to indicate interest in pictures.")
    last_image = tr.Array(shape=(None,None))

    max_period = 0.1

    def __init__(self):
        cam = api.Context()
        cam.connect(cam.camera_from_index(0))
        sinfo = cam.Shutter.info
        ginfo = cam.Gain.info
        super(RealFlyCam,self).__init__(
            _cam = cam,
            connected = True,
            shutter_range = [sinfo.absMin,sinfo.absMax]*pq.ms,
            gain_range = np.exp(_dB2natlog*np.r_[ginfo.absMin,ginfo.absMax])
        )

    def _get_shutter(self):
        return self._cam.Shutter.absValue * pq.ms
    def _set_shutter(self, value):
        self._cam.Shutter.absValue = pq.Quantity(value,pq.ms).manitude

    def _get_gain(self):
        return np.exp(_dB2natlog*self._cam.Gain.absValue)
    def _set_gain(self, value):
        self._cam.Gain.absValue = np.log(value)*_natlog2dB

    def one_pass(self, dt):
#        if not self.enabled_for:
#            return
        img = self._cam.retrieve_buffer()
        data = img.data
        del img
        self.last_image = data

    def startup(self):
        self._cam.start_capture()

    def shutdown(self):
        self._cam.stop_capture()

    def failed(self):
        self.shutdown()

    def reset(self):
        self.stop()
        self.start()


class SimulatedFlyCam(RealFlyCam):
    _cam = tr.Disallow

    shutter = QuantityTrait(pq.ms)
    gain = tr.CFloat

    shape = tr.Array(int,(2,),value=np.r_[1920,1024])

    _pos = tr.Any

    def __init__(self,**kw):
        super(RealFlyCam,self).__init__(**kw)


    def startup(self):
        pass

    def shutdown(self):
        pass

    def one_pass(self, dt):
#        if not self.enabled_for:
#            return
#        data = np.zeros(self.shape[::-1])
        r = 0.05
        x,y = np.meshgrid(*(np.arange(-(s-1)*r/2,s*r/2,r) for s in self.shape))
        pos = self._pos.position.mag_in(pq.um) if self._pos else np.r_[0, 0]
        data = np.exp(-0.5/0.5**2*((x-pos[0])**2+(y-pos[1])**2))
        self.last_image = np.round(data*255).astype('u1')

if api is not None:
    FlyCam = RealFlyCam
else:
    FlyCam = SimulatedFlyCam
