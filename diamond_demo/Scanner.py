import time
import importlib

import numpy as np
import quantities as pq
import traits.api as tr

from yde.lib.quantity_traits import QuantityTrait, QuantityArrayTrait

from .hwctrl.PhotonCounting import TDC
from .hwctrl.Positioning import Positioning
from .hwctrl.FlyCam import FlyCam

#################################################################################

# helper class for Sample size
class Size:
    def __init__(self, height, width):
        self.height = height
        self.width = width

    # override multiplication
    def __mul__(self, other):
        self.width *= other
        self.height *= other
        return self

    # override division
    def __div__(self, other):
        self.width /= other
        self.height /= other
        return self


#################################################################


class FluorescenceMap(tr.HasStrictTraits):
    start = QuantityArrayTrait(pq.um,shape=(2,))
    step = QuantityArrayTrait(pq.um,shape=(2,))
    shape = tr.Array(int,shape=(2,))
    stop = tr.Property(
        handler = QuantityArrayTrait(pq.um,shape=(2,)),
        fget = lambda self:self.start+(self.shape-1)*self.step,
    )
    centre = tr.Property(
        handler = QuantityArrayTrait(pq.um,shape=(2,)),
        fget=lambda self:self.start+0.5*(self.shape-1)*self.step,
    )
    data = QuantityArrayTrait(pq.kHz,shape=(None,None))
    X = tr.Property(QuantityArrayTrait(pq.um,shape=(None,None)))
    Y = tr.Property(QuantityArrayTrait(pq.um,shape=(None,None)))
    extents = tr.Property(
        handler = QuantityArrayTrait(pq.um,shape=(2,2),desc='(x/y,min/max'),
        fget=lambda self:(
            self.start
            + np.c_[[-0.5,-0.5],self.shape-0.5].T*self.step
        ).T,
    )
    region_updated = tr.Event(
        tr.Tuple(tr.Any,tr.Any),
        desc="slice, replacement data"
    )

    @tr.cached_property
    def _get_X(self):
        return self.start[0] + np.tile(np.arange(self.shape[0]),(self.shape[1],1))*self.step[0]

    @tr.cached_property
    def _get_Y(self):
        return self.start[1] + np.tile(np.arange(self.shape[1]),(self.shape[0],1)).T*self.step[1]


    def _data_default(self):
        return np.zeros(self.shape[::-1])


    def config(self):
        # max and min x are half the sample size since we place the sample in such a way that it is centered arround the
        # origin of lens
        self.maxX = self.sampleSize.width / 2.0
        self.minX = -self.sampleSize.width / 2.0

        self.maxY = self.sampleSize.height / 2.0
        self.minY = -self.sampleSize.height / 2.0

        if not hasattr(self, 'xsteps'):
            self.xsteps = np.linspace(0, 0.05, 500)
        if not hasattr(self, 'ysteps'):
            self.ysteps = np.linspace(0, 0.05, 500)

        self.dataArray = np.ones((len(self.ysteps), len(self.xsteps)), dtype=np.float64)

    def update(self,slice,data):
        self.data[slice] = data
        self.region_updated = slice,data


class ScanningRFMeasurement(tr.HasStrictTraits):
    _tdc = tr.Instance(TDC,())
    _pos = tr.Instance(Positioning,kw=dict(
        _theta_terminal = '/Dev2/ao0',
        _phi_terminal = '/Dev2/ao1',
        _focus_terminal = '/Dev2/ao2',
    ))
    _cam = tr.Instance(FlyCam)

    position_offset = QuantityArrayTrait(pq.um,shape=(2,))
    position = tr.Property(
        handler = QuantityArrayTrait(pq.um,shape=(2,)),
    )
    _focus_end = QuantityTrait(5*pq.V)
    focus = tr.Property(
        handler = QuantityTrait(pq.V)
    )
    background_rate = QuantityTrait(pq.kHz)

    auto_optimisation = tr.Bool
    optimisation_interval = QuantityArrayTrait(30*pq.s)
    _last_optim = tr.CFloat()
    _optim_step = QuantityTrait(0.1*pq.um)
    _optim_size = tr.Int(6)
    _last_hbt = tr.CFloat()
    mode = tr.Enum('idle','mapping', 'on_target', 'optimising', 'hbt')
    _cur_map = tr.Instance(FluorescenceMap)
    _cur_idx = tr.Array(int,shape=(2,))
    new_hbt = tr.Event

    # scanner class: needs sampleSize (to calculate the max and min angles for the galvo) and
    #               the distance from the galvo to the lens

    # arguments: all units in mm, devicePhi for Xtranslation, devicetheta for Ytranslation
    def __init__(self, **kw):
        kw.setdefault('focus',0*pq.V)
        super(ScanningRFMeasurement,self).__init__(**kw)
        self._pos
        self._tdc.reset()

        if False:
            self.initCamera()
            # if we have a focus point set it
            # init the piezo to full focal
            self.dataArray = np.ones((len(self.ysteps), len(self.xsteps)), dtype=np.float64)
            self.setFocus(0)
            if hasattr(self, "focus"):
                self.setFocus(self.focus)
            if (hasattr(self, "imageSettings")):
                self.setImageProperties(self.imageSettings['gain'], self.imageSettings['shutter'])
            time.sleep(2)


    def _get_position(self):
        return self._pos.position - self.position_offset
    def _set_position(self, position):
        self._pos.position =  position + self.position_offset
    @tr.on_trait_change('_pos:position,position_offset')
    def _position_changes(self):
        self.trait_property_changed('position',self._get_position())

    def _get_focus(self):
        return self._focus_end - self._pos.piezo_voltage
    def _set_focus(self, focus):
        self._pos.piezo_voltage =  self._focus_end - focus
    @tr.on_trait_change('_pos:piezo_voltage,_focus_end')
    def _focus_changes(self):
        self.trait_property_changed('focus',self._get_focus())

    def deinit(self):
        self._tdc.deinit()
        self._pos._release_tasks()
        del self._tdc
        del self._pos
        del self._cam

    def stop(self):
        self.mode = 'idle'

    def _mode_changed(self,old,new):
        self._tdc.freeze = new != 'hbt'
        if new == 'optimising':
            map = FluorescenceMap(
                shape = (self._optim_size, self._optim_size),
                step = (self._optim_step, self._optim_step)
            )
            map.centre = self.position
            self._scan_map(map)

    @tr.on_trait_change('_tdc:new_data')
    def _got_new_data(self, rates):
        from yde.lib.py2to3 import monotonic
        if self.mode in ['mapping','optimising']:
            cm = self._cur_map
            ci = self._cur_idx
            cm.update(tuple(ci),rates.sum())
            if ci[0]&1:
                if ci[1]:
                    ci[1] -= 1
                else:
                    ci[0] += 1
            else:
                if ci[1]+1<cm.shape[1]:
                    ci[1] += 1
                else:
                    ci[0] += 1
            if ci[0]>=cm.shape[0]:
                self._cur_map = None
                if self.mode=='optimising':
                    self._process_optimisation(cm)
                self.mode=dict(
                    mapping='idle',
                    optimising='hbt' if self._tdc.enable_HBT else 'on_target'
                )[self.mode]
            else:
                tci = tuple(ci)
                self.position = cm.X[tci], cm.Y[tci]
        elif self.mode in ['on_target', 'hbt']:
            now = monotonic()
            if self.mode == 'hbt':
                if self._last_hbt + 1 <= now:
                    self.new_hbt = self._tdc.hbt
                    self._last_hbt = now
            if self.auto_optimisation and self._last_optim + self.optimisation_interval.mag_in(pq.s) <= now:
                self.mode = 'optimising'

    def _process_optimisation(self, map):
        from yde.lib.py2to3 import monotonic

        min,max = map.data.min(), map.data.max()
        isum = 1/map.data.sum()
        x = (map.X * map.data).sum()*isum
        y = (map.Y * map.data).sum()*isum
        drift = pq.asanyarray([x,y]) - map.centre
        print('optimisation: ',min,max,drift)
        self.position_offset += drift
        self.position = map.centre
        self._last_optim = monotonic()

    def _scan_map(self,map):
        self._cur_idx = 0,0
        self._cur_map = map
        self.position = map.X[0,0], map.Y[0,0]

    def choose_point(self, point):
        self.position = point
        self.mode = 'optimising'

    def setup_hbt(self, reso, range):
        self._tdc.enable_HBT = True
        self._tdc.setup_hbt(reso,range)
        self.mode = 'hbt'