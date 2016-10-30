__author__ = 'yves'

import numpy as np
import quantities as pq
import traits.api as tr

from yde.labdev.flycap import api
from yde.lib.quantity_traits import QuantityTrait, QuantityArrayTrait
from yde.lib.threading import RepeatingTaskRunner

_dB2natlog = np.log(10)/10
_natlog2dB = 10/np.log(10)

class FlyCam(RepeatingTaskRunner):
    _cam = tr.Instance(api.Context)

    connected = tr.Bool(desc='read only')

    shutter = tr.Property(
        QuantityTrait(pq.ms),
    )
    shutter_range = QuantityArrayTrait(pq.ms,shape=(2,))
    gain = tr.Property(
        tr.CFloat(desc='gain factor')
    )
    gain_range = tr.Array(float,shape=(2,))

    new_image = tr.Event(tr.Array(float,(None,None)))

    max_period = 0.1

    def __init__(self):
        cam = api.Context()
        cam.connect(cam.camera_from_index(0))
        sinfo = cam.Shutter.info
        ginfo = cam.Gain.info
        super(FlyCam,self).__init__(
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
        img = self._cam.retrieve_buffer()
        data = img.data / 255.
        del img
        self.new_image = data

    def startup(self):
        self._cam.start_capture()

    def shutdown(self):
        self._cam.stop_capture()

    def failed(self):
        self.shutdown()

    def reset(self):
        self.stop()
        self.start()
