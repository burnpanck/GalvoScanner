import time
import importlib

import numpy as np
import quantities as pq
import traits.api as tr

from yde.lib.quantity_traits import QuantityTrait, QuantityArrayTrait

from .hwctrl.PhotonCounting import TDC
from .hwctrl.Positioning import Positioning
from .hwctrl.FlyCam import FlyCam

#################################################################


class FluorescenceMap(tr.HasStrictTraits):
    step = QuantityArrayTrait(pq.um,shape=(2,))
    shape = tr.Array(int,shape=(2,))
    centre = QuantityArrayTrait(pq.um,shape=(2,))
    start = tr.Property(
        handler = QuantityArrayTrait(pq.um,shape=(2,)),
        fget = lambda self:self.centre-0.5*(self.shape-1)*self.step,
        depends_on = 'centre,shape,step',
    )
    stop = tr.Property(
        handler = QuantityArrayTrait(pq.um,shape=(2,)),
        fget = lambda self:self.centre+0.5*(self.shape-1)*self.step,
        depends_on = 'centre,shape,step',
    )
    data = QuantityArrayTrait(pq.kHz,shape=(None,None))
    X = tr.Property(
        QuantityArrayTrait(pq.um,shape=(None,None)),
        depends_on = 'centre,shape,step'
    )
    Y = tr.Property(
        QuantityArrayTrait(pq.um,shape=(None,None)),
        depends_on = 'centre,shape,step'
    )
    extents = tr.Property(
        handler = QuantityArrayTrait(pq.um,shape=(2,2),desc='(x/y,min/max'),
        fget=lambda self:(
            self.centre
            + np.r_[-0.5,0.5][:,None]*self.shape*self.step
        ).T,
        depends_on = 'centre,shape,step',
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
        return np.zeros(self.shape[::-1]) * pq.kHz
        
    def _data_changed(self, new):
        self.region_updated = np.s_[:,:], new

    def _shape_changed(self):
        self.data = self._data_default()

    def update(self,slice,data):
        self.data[slice] = data
        self.region_updated = slice,data


class ScanningRFMeasurement(tr.HasStrictTraits):
    _tdc = tr.Instance(TDC,())
    _pos = tr.Instance(Positioning,kw=dict(
        _theta_terminal = '/Dev1/ao0',
        _phi_terminal = '/Dev1/ao1',
        _focus_terminal = '/Dev1/ao2',
    ))
    _cam = tr.Instance(FlyCam)

    position_offset = QuantityArrayTrait(pq.um,shape=(2,))
    position = tr.Property(
        handler = QuantityArrayTrait(pq.um,shape=(2,)),
        depends_on = '_pos:position,position_offset',
    )
    _focus_end = QuantityTrait(5*pq.V)
    focus = tr.Property(
        handler = QuantityTrait(pq.V),
        depends_on = '_pos:piezo_voltage,_focus_end',
    )
    signal_ratio = tr.DelegatesTo('_tdc')
    auto_correction = tr.Bool

    auto_optimisation = tr.Bool
    optimisation_interval = QuantityArrayTrait(30*pq.s)
    _last_optim = tr.CFloat()
    _optim_step = QuantityTrait(0.1*pq.um)
    _optim_size = tr.Int(7)
    _last_hbt = tr.CFloat()
    mode = tr.Enum('idle','mapping', 'on_target', 'optimising', 'hbt')
    hbt_force = tr.Bool()
    _previous_mode = tr.Enum('idle','mapping', 'on_target', 'optimising', 'hbt')
    _cur_map = tr.Instance(FluorescenceMap)
    _cur_idx = tr.Array(int,shape=(2,))
    new_hbt = tr.Event

    fb_map = tr.Instance(FluorescenceMap)    
    
    # scanner class: needs sampleSize (to calculate the max and min angles for the galvo) and
    #               the distance from the galvo to the lens

    # arguments: all units in mm, devicePhi for Xtranslation, devicetheta for Ytranslation
    def __init__(self, **kw):
        kw.setdefault('focus',0*pq.V)
        super(ScanningRFMeasurement,self).__init__(**kw)
        self._pos

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

    def _get_focus(self):
        return self._focus_end - self._pos.piezo_voltage
    def _set_focus(self, focus):
        self._pos.piezo_voltage =  self._focus_end - focus

    def _fb_map_default(self):
        return FluorescenceMap(
            shape = (self._optim_size, self._optim_size),
            step = (self._optim_step, self._optim_step)
        )
        
    def deinit(self):
        self._tdc.deinit()
        self._pos._release_tasks()
        del self._tdc
        del self._pos
        del self._cam

    def stop(self):
        self.mode = 'idle'

    def _mode_changed(self,old,new):
        self._previous_mode = old
        self._tdc.freeze = (not self.hbt_force) and new != 'hbt'
        if new == 'optimising':
            map = self._fb_map_default()
            map.centre = self.position
            self._scan_map(map)
            self.fb_map = map

    def _hbt_force_changed(self,new):
        self._tdc.freeze = (not new) and self.mode != 'hbt'

    @tr.on_trait_change('_tdc:new_data')
    def _got_new_data(self, rates):
        from yde.lib.py2to3 import monotonic
        now = monotonic()
        try:
            if self.mode in ['mapping','optimising']:
                cm = self._cur_map
                ci = self._cur_idx
                if ci[1]>=0:
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
                        optimising='hbt' if self._previous_mode=='hbt' else 'on_target'
                    )[self.mode]
                else:
                    tci = tuple(ci)
                    self.position = pq.asanyarray([cm.X[tci], cm.Y[tci]])
            elif self.mode in ['on_target', 'hbt']:
                if self.auto_optimisation and self._last_optim + self.optimisation_interval.mag_in(pq.s) <= now:
                    self.mode = 'optimising'
        except Exception:
            self.mode = 'idle'
            raise
        try:
            if self.hbt_force or  self.mode == 'hbt':
                if self._last_hbt + 1 <= now:
                    self.new_hbt = self._tdc.hbt
                    self._last_hbt = now
        except Exception as ex:
            print(ex)

    def _process_optimisation(self, map):
        from yde.lib.py2to3 import monotonic
        from scipy.stats import scoreatpercentile

        min,max = map.data.min(), map.data.max()
        data = map.data
        bg = scoreatpercentile(data,20)
        bg = data[data<=bg].mean()
        data = data - bg
        norm = 1/data.mean()
        xs = (map.X * data).mean()
        ys = (map.Y * data).mean()
        x = xs*norm
        y = ys*norm
        drift = pq.asanyarray([x,y]) - map.centre
        print('optimisation: ',min,bg,max,drift,xs,ys,1/norm)
        if self._previous_mode == 'idle':
            self.position = map.centre + drift
        else:
            self.position_offset += drift
            self.position = map.centre
        if self.auto_correction:
            self.signal_ratio = (max-bg)/max
        self._last_optim = monotonic()

    def _scan_map(self,map):
        self._cur_idx = 0,-1
        self._cur_map = map
        self.position = pq.asanyarray([map.X[0,0], map.Y[0,0]])

    def scan(self, map):
        self.position_offset = (0,0)*pq.um
        self._scan_map(map)
        self.mode = 'mapping'
        
    def choose_point(self, point):
        self.mode = 'idle'
        self.position = point
        self.mode = 'optimising' if self.auto_optimisation else 'on_target'

    def setup_hbt(self, reso, range):
        self._tdc.enable_HBT = True
        self._tdc.setup_hbt(reso,range)
        self.mode = 'hbt'