import sys

from functools import partial
import time
import traceback
import importlib
import os.path
import abc
import datetime
import types
import logging

from PyQt5.QtCore import pyqtSignal, pyqtSlot, QObject
from PyQt5.QtGui import QPalette, QImage, QPixmap, qRgba
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QMessageBox,
    QHBoxLayout, QVBoxLayout, QGridLayout,
    QPushButton, QCheckBox, QLineEdit, QLabel, QSlider,
    QSpinBox, QDoubleSpinBox, QProgressBar,
    QSizePolicy,
    QFileDialog,
    QGraphicsScene, QGraphicsItem, QGraphicsPixmapItem,
)

import numpy as np
import quantities as pq
import traits.api as tr

import matplotlib as mpl
mpl.use('Qt5Agg')
import matplotlib.axes
import matplotlib.backends.backend_qt5agg

from yde.lib.misc.basics import Struct
from yde.lib.quantity_traits import QuantityTrait, QuantityArrayTrait
from yde.lib.traits_ext import declared_trait, trait_type

from .Scanner import ScanningRFMeasurement, FluorescenceMap

def catch2messagebox(fun):
    """ wrap function to display a message when an exception happens
    """
    def wrapper(*args,**kw):
        try:
            fun(*args,**kw)
        except Exception as ex:
            # TODO: fix messagebox
            ans = QMessageBox.critical(
                None, 'Exception!',
                traceback.format_exc(),
            )
            raise
    return wrapper

def handle_traits_error(object, trait_name, old_value, new_value):
    print(
        'Failed to set trait "%s" of %s object to %s (was %s):\n'%(
            trait_name, type(object).__name__, new_value, old_value
        )+''.join(traceback.format_exc())
    ) # TODO: messagebox
    raise

class Signal(QObject):
    signal = pyqtSignal()

    def __init__(self):
        super(Signal,self).__init__()

    def connect(self, cb):
        return self.signal.connect(cb)

    def emit(self):
        self.signal.emit()

class QtFigure(tr.HasTraits):
    ax = tr.Instance(mpl.axes.Axes)
    canvas = tr.Instance(mpl.backends.backend_qt5agg.FigureCanvasQTAgg)
    update = tr.Callable
    _notifier = tr.Instance(Signal)
    _busy = tr.Bool()

    button_press_event = tr.Event
    
    def __init__(self, parent, fig=dict(), ax=dict(), *, left=0.1, right=0.1, top=0.1, bottom=0.1, **kw):
        for k in 'figsize dpi'.split():
            if k in kw:
                fig[k] = kw.pop(k)

        for k in 'xlabel ylabel'.split():
            if k in kw:
                ax[k] = kw.pop(k)
        if False:
            bgc = parent.palette().color(QPalette.Background)
        fig.setdefault(
            'facecolor',
#            (bgc.red()/255,bgc.green()/255,bgc.blue()/255)
            'none'
        )
        f = mpl.figure.Figure(**fig)
        ax = f.add_axes([left,bottom,1-left-right,1-bottom-top],**ax)
        canvas = mpl.backends.backend_qt5agg.FigureCanvasQTAgg(f)
        layout = QHBoxLayout(parent)
        layout.addWidget(canvas)

        canvas.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        canvas.updateGeometry()


        def connect(e,canvas,obj):
            canvas.mpl_connect(e, lambda v: setattr(obj,e,v))
        for e in 'button_press_event'.split():
            connect(e,canvas,self)

        sig = Signal()
        sig.connect(self._do_update)
        kw.update(
            ax = ax,
            canvas = canvas,
            _notifier = sig,
        )
         
        super(QtFigure, self).__init__(**kw)

    def request_update(self):
        if not self._busy:
            self._busy = True
            self._notifier.emit()

    @pyqtSlot()
    def _do_update(self):
        if not self.update:
            return
        self.update(self)
        self.canvas.draw()
        self._busy = False

class QtTraitLinkMeta(type(tr.ABCHasStrictTraits)):
    def __new__(mcls, cls, bases, dct):
        ret = super().__new__(mcls,cls,bases,dct)
        ret._link_classes[ret._ui_class,ret._trait_type] = ret
        return ret

class QtTraitLink(tr.ABCHasStrictTraits,metaclass=QtTraitLinkMeta):
    _ui_class = QWidget
    _trait_type = (tr.TraitType,)
    _link_classes = {}

    obj = tr.Instance(tr.HasTraits)
    trait = tr.Str
    ui = tr.Any
    auto_update = tr.Bool(True)
    _notifier = tr.Instance(Signal)

    ui_changed = tr.Event(desc="emitted when the UI changes, which might not yet have been reflected on the trait")

    @classmethod
    def connect(cls,obj,trait,ui,**kw):
        if cls is QtTraitLink:
            # determine subclass from trait type and ui class
            t = trait_type(obj, trait)
            if t is None or isinstance(t,tr.CTrait):
                print('Warning: unknown trait type for attributen ',trait,t)
                t = tr.TraitType()
            choice = None
            umro = type(ui).__mro__
            tmro = type(t).__mro__
#            print('Looking for link',ui,umro,t,tmro)
            for (uicls,traittype),linkcls in cls._link_classes.items():
#                print(linkcls,isinstance(ui,uicls),isinstance(t,traittype))
                if not isinstance(ui,uicls):
                    continue
                if not isinstance(t,traittype):
                    continue
                idx = (
                    umro.index(uicls) if not isinstance(uicls,tuple) else min(umro.index(c) for c in uicls),
                    tmro.index(traittype) if not isinstance(traittype,tuple) else min(tmro.index(c) for c in traittype),
                )
#                print(idx,choice)
                if choice is None or all(a<=b for a,b in zip(idx,choice[0])):
                    choice = idx,linkcls
                elif not all(a>=b for a,b in zip(idx,choice[0])):
                    raise TypeError('Ambiguous link ',trait,ui,t,(idx,linkcls),choice)
            if choice is None or choice[1] is QtTraitLink:
                raise TypeError('No matching link ',trait,ui,t)
            # second chance for subclasses
            return choice[1].connect(obj,trait,ui,**kw)
        traits = dict()
        for k in cls.class_editable_traits():
            if k in kw:
                traits[k] = kw.pop(k)
        sig = Signal()
        ret = cls(obj=obj,trait=trait,_notifier=sig,ui=ui,**traits)
        ret._set(getattr(obj,trait))
        sig.connect(ret._do_update)
        ret._connect_ui()
        obj.on_trait_change(
            ret._request_update,
            ret.trait
        )
        return ret
    
     
    def _request_update(self):
        self._notifier.emit()
     
    @pyqtSlot()
    def _do_update(self):
        new = getattr(self.obj, self.trait)
#        print('update gui ',self.trait,new)
        self._set(new)
    
    def _update_trait(self, *args, **kw):
        try:
            new = self._get()
        except Exception as ex:
            print('failed update of "%s":%s'%(self.trait,ex))
            return
        self.ui_changed = new
        if not self.auto_update:
            return
#        print('_update traits')
 #       print('update trait ',self.trait,args,kw,new)
        setattr(self.obj, self.trait, new)

    @abc.abstractmethod
    def _connect_ui(self,**ui): pass
    
    @abc.abstractmethod
    def _set(self, val): pass
    
    @abc.abstractmethod
    def _get(self): pass

class QCheckBoxLk(QtTraitLink):
    _ui_class = QCheckBox

    auto_update = True

    def _connect_ui(self):
        self.ui.stateChanged.connect(self._update_trait)

    def _set(self, val):
        self.ui.setChecked(val)
    def _get(self):
        return self.ui.isChecked()

class QLabelLk(QtTraitLink):
    _ui_class = QLabel

    def _connect_ui(self):
        pass

    def _set(self, val):
        self.ui.setText(self._fmt(val))
    def _get(self):
        return self._parse(self.ui.text())

    def _fmt(self, val):
        return val

    def _parse(self, val):
        return val


class QLineEditLk(QtTraitLink):
    _ui_class = QLineEdit

    def _connect_ui(self):
        self.ui.textChanged.connect(self._update_trait)

    def _set(self, val):
        text = self.ui.text()
        ntext = self._fmt(val)
        if text == ntext:
#            print('not updating, no change in text',text,val,ntext)
            return
        try:
            pval = self._parse(text)
        except Exception as ex:
            pass
        else:
            if pval == val:
#                print('Not updating, no change in value!',pval,text,val,ntext)
                return
#Y            print('do set',pval,text,val,ntext)
        self.ui.setText(self._fmt(val))
    def _get(self):
        text = self.ui.text()
        try:
            return self._parse(text)
        except Exception as ex:
            import traceback
            print('Cannot parse "%s"'%text,ex)
            raise

    def _fmt(self, val):
        return val

    def _parse(self, val):
        return val


class QIntSpinBoxLk(QtTraitLink):
    _ui_class = QSpinBox

    def _connect_ui(self):
        self.ui.valueChanged[int].connect(self._update_trait)

    def _set(self, val):
        self.ui.setValue(val)

    def _get(self):
        return self.ui.value()

class QProgressBarLk(QtTraitLink):
    _ui_class = QProgressBar

    def _connect_ui(self):
        pass

    def _set(self, val):
        self.ui.setValue(val)

    def _get(self):
        return self.ui.value()


class QDblSpinBoxLk(QtTraitLink):
    _ui_class = QDoubleSpinBox

    def _connect_ui(self):
        self.ui.valueChanged[float].connect(self._update_trait)

    def _set(self, val):
        self.ui.setValue(val)

    def _get(self):
        return self.ui.value()


class QtQuantitySpinBoxLk(QDblSpinBoxLk):
    _trait_type = (QuantityTrait,)

    def _set(self, val):
        unit = self.ui.property('hidden_unit')
#        print('hidden unit for ',self.trait,unit)
        if not unit:
            self.ui.setSuffix(' '+str(val.units.dimensionality))
            self.ui.setValue(val.magnitude)
        else:
            self.ui.setValue(val.mag_in(unit))

    def _get(self):
        unit = self.ui.property('hidden_unit')
        if not unit:
            unit = self.ui.suffix().strip()
        return self.ui.value() * getattr(pq,unit)

class QtLogHandler(logging.Handler):
    def __init__(self, widget=None, level=logging.DEBUG):
        logging.Handler.__init__(self)
        self.widget = widget
        self.level = level
        self._queue = []
        self._sig = Signal()
        self._sig.connect(self._do_update)

    def flush(self):
        """
        does nothing for this handler
        """

    def emit(self, record):
        """
        Emit a record.

        """
        try:
            msg = self.format(record)
            self._queue.append(msg)
            self._sig.emit()
        except (KeyboardInterrupt, SystemExit):
            raise
        except:
            self.handleError(record)

    @pyqtSlot()
    def _do_update(self):
        q = self._queue
        if not q:
            return
        self._queue = []
        self.widget.appendHtml('<br>'.join(m for m in q))

class ScanGui(tr.HasStrictTraits):
    _s = tr.Instance(ScanningRFMeasurement)
    _frame = tr.Instance(QWidget)
    _tk_objects = tr.Dict(tr.Str,tr.Any)
    _map_fig = tr.Instance(QtFigure)
    _fb_map_fig = tr.Instance(QtFigure)
    _rate_fig = tr.Instance(QtFigure)
    _HBT_fig = tr.Instance(QtFigure)
    _trait_gui_links = tr.List(tr.Instance(QtTraitLink))

    _cam_fig = tr.Any
    _cam_img = tr.Any(None)
    _new_cam_img = tr.Instance(Signal)


    focus = tr.DelegatesTo('_s')
    mode = tr.DelegatesTo('_s')
    position = tr.DelegatesTo('_s')
    auto_optimisation = tr.DelegatesTo('_s')
    auto_correction = tr.DelegatesTo('_s')
    hbt_force = tr.DelegatesTo('_s')
    autoscale = tr.Bool(True)
    normalise = tr.Bool(True)
    correct = tr.Bool(True)
    map = tr.Instance(FluorescenceMap,kw=dict(
        shape = (10,10),
        step = (0.5,0.5)*pq.um,
    ))
    fb_map = tr.DelegatesTo('_s')
    rate_trace = QuantityArrayTrait(np.zeros(100)*pq.kHz,shape=(None,))
    last_HBT = tr.Any

    save_dir = tr.Directory()

    # ------new traits
    # --- overal status
    system_status = tr.DelegatesTo('_s','mode')

    galvoX = tr.Property(
        trait = QuantityTrait(pq.um),
        fget = lambda self: self._s.position[0],
        fset = lambda self,v: setattr(self._s,'position',pq.asanyarray([v,self._s.position[1]])),
        depends_on = '_s.position',
    )
    galvoY = tr.Property(
        trait = QuantityTrait(pq.um),
        fget = lambda self: self._s.position[1],
        fset = lambda self,v: setattr(self._s,'position',pq.asanyarray([self._s.position[0],v])),
        depends_on = '_s.position',
    )
    piezo_voltage = tr.DelegatesTo('_s','focus')

    enable_drift_cancel = tr.DelegatesTo('_s','auto_optimisation')
    drift_cancel_interval = tr.DelegatesTo('_s','optimisation_interval')

    autoscale_rate_plot = tr.Bool(True)

    # --- mapping page
    mapping_range = QuantityTrait(2*pq.um)
    mapping_resolution = QuantityTrait(0.1*pq.um)
    mapping_scaling = tr.Int(2)
    enable_multiscale = tr.Bool(True)

    scan_progress = tr.DelegatesTo('_s')

    map_clim_lo = QuantityTrait(pq.kHz)
    map_clim_hi = QuantityTrait(pq.kHz)
    autoscale_map = tr.Bool(True)

    # --- hbt page
    enable_hbt = tr.Bool(True)
    force_hbt = tr.DelegatesTo('_s','hbt_force')
    #clear_hbt button
    hbt_range = QuantityTrait(100*pq.ns)
    hbt_resolution = QuantityTrait(1*pq.ns)
    #reset_hbt
    normalise_hbt = tr.Bool(True)
    auto_snr = tr.Bool(False)
    signal_ratio = tr.DelegatesTo('_s')
    subtract_background = tr.Bool(False)
    #save_hbt



    @classmethod
    @catch2messagebox
    def main(cls,**kw):
        try:
            tr.push_exception_handler(
                handle_traits_error,
                reraise_exceptions=False,
                main=True
            )
            app = QApplication([])
            self = cls(**kw)
            ec = app.exec_()
            self.deinit()
        finally:
            tr.pop_exception_handler()
        return ec

    def deinit(self):
        self._s.deinit()

    @classmethod
    def _handle_cfg(cls, obj, settings):
        for k,v in settings.items():
            t = trait_type(obj,k)
            if isinstance(t,tr.Instance):
                cls._handle_cfg(getattr(obj, k), v)
                continue
            if isinstance(t,QuantityArrayTrait) and isinstance(v,str):
                value,unit = v.rsplit(None,1)
                v = eval(value)*getattr(pq,unit)
            setattr(obj, k, v)
        
    def load_config(self, configFile):
        import json
        configFile = os.path.abspath(configFile)
        path = os.path.dirname(configFile)
        with open(configFile,'r') as fh:
            cfg = json.loads(fh.read())
        for cfgfile in cfg.pop("imports",[]):
            cfg.update(self.load_config(os.path.join(path,cfgfile)))
        for key, obj in zip(
            'gui galvo qupsi scanner'.split(),
            [self, self._s._pos, self._s._tdc, self._s],
        ):
            self._handle_cfg(obj, cfg.pop(key, {}))
        return cfg

    def __init__(self, config_file=None, **kw):
        scanner_kw = dict()
        for k in ''.split():
            v = kw.pop(k,None)
            if v is not None:
                scanner_kw[k] = v
        super(ScanGui,self).__init__(**kw)
        self._s = ScanningRFMeasurement(**scanner_kw)
        if config_file is not None:
            self.load_config(config_file)
        self._create_frame()
        self._s._tdc.reset()
        self._s._cam.reset()

    def reconnect_quPSI(self):
        print('reconnect quPSI')
        self._s._tdc.reset()

    def center_galvo(self):
        self._s.position = np.zeros(2,)*pq.um

    def start_scan(self):
        self.map.shape = np.tile(np.round(pq.unitless(
            self.mapping_range/self.mapping_resolution
        )).astype(int),2)
        self.map.step = np.r_[1,1] * self.mapping_resolution
        self._s.scan(self.map,self.mapping_scaling if self.enable_multiscale else 0)

    def clear_hbt(self):
        pass

    def reset_hbt(self):
        self._s.setup_hbt(self.hbt_resolution, self.hbt_range)

    def save_hbt(self):
        pass

    def _create_frame(self):

        from PyQt5 import uic

        mainwnd = uic.loadUi(os.path.join(os.path.dirname(__file__),'..','MainWindow.ui'))
        self._frame = mainwnd
        cls = type(self)
        links = []
        for k,v in mainwnd.__dict__.items():
            t = self.trait(k)
            a = getattr(self, k, None)
            if isinstance(v,QPushButton):
                if not isinstance(a,types.MethodType):
                    print('Could not find callback handler for button "%s": %s'%(k,type(a).__name__))
                else:
                    v.clicked.connect(a)
            elif t is not None:
                print('Linking trait "%s": %s'%(k,t))
                links.append(QtTraitLink.connect(obj=self,trait=k,ui=v))
            else:
                print('Ignoring unknown "%s": %s' % (k, a))
        self._trait_gui_links = links

        self._create_scan_plot(mainwnd.map_widget)
        self._create_cam_plot(mainwnd.ccd_image_widget)
        self._create_rate_plot(mainwnd.rate_plot_widget)
        self._create_drift_cancel_plot(mainwnd.drift_cancel_widget)
        self._create_HBT_plot(mainwnd.hbt_widget)

        loghandler = QtLogHandler(mainwnd.log_widget,level=logging.DEBUG)
#        loghandler.setFormatter(logging.Formatter())
        logging.root.addHandler(loghandler)

        logging.getLogger('ScanGui').info('UI ready')
        mainwnd.show()
        return

        # add our gui to the master Widget
        wnd = QMainWindow()
        statusbar = wnd.statusBar()

        widget = QWidget()
        wnd.setCentralWidget(widget)
        widget.setWindowTitle('ConfocalScan')

        s = Struct()
        cb = catch2messagebox

        s.modestatus = QtStrLk.make(None,self,'mode',readonly=True)
        statusbar.addPermanentWidget(s.modestatus.ui)

        grid = QGridLayout(widget)

        # we need one slider for focus
        # self.scaleLabel = Label(frame, text="Focus: ")
        # self.scaleLabel.grid(row=0, column=0)
        s.focus = QtQuantityLk.make(grid, self, 'focus', unit=pq.V, row=0, column=0)

        def make_button(text,row,column,cb):
            b = QPushButton(text=text)
            grid.addWidget(b,row,column)
            b.clicked.connect(cb)
            return b

        if False:
            s.focusSet = make_button(
                "Set Focus",0,1,
                lambda val: self.trait_set(focus=float(s.focus.ui.text()) * pq.V)
            )

        for line in """
            autoscale           3 5 Autoscale; Auto-scale detection rate plot
            correct             3 6 Subtract background; Use current estimate of SNR to subtract a constant background from g(2), assuming uncorrelated background events
            auto_correction     2 8 Determine SNR; Automatically update signal to noise ratio from drift correction scans
            normalise           3 8 Normalise; Normalise g(2) function to 1 at long delays
            auto_optimisation   4 8 Correct for drift; Periodically check for drift and adjust detection position when necessary
            hbt_force           6 8 Force HBT; Force accumulation of coincidence events even when usually disabled, e.g. when mapping or performing drift cancellation
        """.split('\n'):
            if not line.strip():
                continue
            parts = line.split(None,3)
            if len(parts) < 4:
                parts.append(parts[0])
            trait,row,column,name = parts
            if ';' in name:
                name, tip = (s.strip() for s in name.split(';',1))
            else:
                tip = None
            setattr(s,trait,QtTraitLink.make(grid,self,trait,row=int(row),column=int(column),text=name,toolTip=tip))

        s.bgrateVar = QtTraitLink.make(grid,self,'signal_ratio',row=3,column=7)

        s.rcQuTau = make_button("Reconnect quPSI",1,1,self._s._tdc.reset)

        s.openConfig = make_button(
            "Open Config File", 1, 0,
            self.open_config,
        )

        s.startScan = make_button(
            "Start Scan", 2, 0,
            lambda: self._s.scan(self.map),
        )

        s.stopScan = make_button(
            "Stop Scan", 2, 1,
            self._s.stop,
        )

        s.resetPos = make_button(
            "Goto 0/0", 3, 4,
            lambda: self._s.trait_set(position=(0,0)*pq.um),
        )

        # TODO: HBT setup params
        s.hbtButton = make_button(
            "Reset HBT", 1, 5,
            lambda: self.reset_hbt(
                float(s.binWidth.get())*pq.ns,
                float(s.binCount.get())*pq.ns,
            ),
        )

        s.hbtStop = make_button("Stop HBT",1,7,self.stop_hbt)

        s.saveDir = QtStrLk.make(grid,self,'save_dir',row=5,column=7)
        s.selectDataDir = make_button("Select folder",5,8,self.select_data_dir)
        s.saveData = make_button("Save data",6,7,self.save_data)

        if False:
            # Xslider
            s.xVar = Tk.StringVar()
            self.on_trait_change(
                lambda pos: s.xVar.set(str(pos[0].mag_in(pq.um))),
                'position'
            )
            s.yVar = Tk.StringVar()
            self.on_trait_change(
                lambda pos: s.yVar.set(str(pos[1].mag_in(pq.um))),
                'position'
            )
            self.trait_property_changed('position',self.position)
            s.xEntry = Tk.Entry(frame, textvariable=s.xVar)
            s.xEntry.grid(row=0, column=5)
            s.yEntry = Tk.Entry(frame, textvariable=s.yVar)
            s.yEntry.grid(row=0, column=6)
            s.setPos = Tk.Button(
                frame, text="Set Position",
                command=cb(lambda: self.trait_set(position=np.r_[
                    float(s.xVar.get()),
                    float(s.yVar.get()),
                ]*pq.um))
            )
            s.setPos.grid(row=0, column=7)

            # position correcture
            s.poscorrVar = Tk.StringVar()
            self.on_trait_change(
                lambda mode: s.poscorrVar.set(mode),
                '_s.position_offset'
            )
            self._s.trait_property_changed('position_offset',self._s.position_offset)
            s.poscorrLbl = Tk.Label(frame, textvariable=s.poscorrVar)
            s.poscorrLbl.grid(row=1, column=6)

            s.angleButton = Tk.Button(frame, text="Show Voltage", command=cb(self.show_galvo_voltages))
            s.angleButton.grid(row=1, column=8)

            # entry fields for binWidth and binCount
            s.binWidth = Tk.StringVar()
            s.binCount = Tk.StringVar()
            s.widthlabel = Tk.Label(frame, text="Time Resolution")
            s.countLabel = Tk.Label(frame, text="range")
            s.widthEntry = Tk.Entry(frame, textvariable=s.binWidth)
            s.countEntry = Tk.Entry(frame, textvariable=s.binCount)
            s.binCount.set("100")
            s.binWidth.set("1")
            s.widthlabel.grid(row=0, column=3)
            s.widthEntry.grid(row=0, column=4)
            s.countLabel.grid(row=1, column=3)
            s.countEntry.grid(row=1, column=4)



            frame.config()

        self._create_scan_plot(grid)
        self._create_rate_plot(grid)
        self._create_drift_cancel_plot(grid)
        self._create_HBT_plot(grid)

        self._frame = wnd
        wnd.show()

    def _create_cam_plot(self, parent):
        self._new_cam_img = Signal()
        self._new_cam_img.connect(self._update_cam_image)
        self._cam_fig = parent

    @tr.on_trait_change('_s:_cam:last_image')
    def _ccd_image_changed(self, event):
        if not self._cam_fig or self._cam_img:
            return
        from matplotlib.cm import magma
        assert event.dtype == np.dtype('u1')
        assert event.ndim == 2
        ctbl = np.round(magma(np.linspace(0,1,256))*255)
        if False:
            ctbl = ctbl.astype('u1')[:,[2,1,0,3]].ravel()
            print(ctbl.shape,ctbl.view('<u4').shape)
            ctbl = ctbl.view('<u4')
        elif False:
            ctbl = np.sum(ctbl.astype('u4')<<[16,8,0,24],-1,dtype='u4')
        else:
            ctbl = [qRgba(*c) for c in ctbl]
        img = QImage(bytes(event),event.shape[1],event.shape[0],QImage.Format_Indexed8)
        img.setColorTable(ctbl)
        print('there is a new image')
        self._cam_img = img # QPixmap.fromImage(img)
        self._new_cam_img.emit()

    def _update_cam_image(self):
        img = self._cam_img
        self._cam_fig.image = img
        print('request update')
        self._cam_fig.update()
        self._cam_img = None

    def _create_scan_plot(self, parent):
        f = QtFigure(
            parent,
            xlabel='',ylabel='',
            left=0.12,bottom=0.07,
            top = 0.04, right=0.04,
            update=self._update_map_image,
        )

        xr,yr = self.map.extents.mag_in(pq.um)
        data = self.map.data.magnitude
        f.img = f.ax.pcolorfast(
            xr,yr,data,
            animated=True,
            cmap='afmhot',
        )
        nowhere = np.tile(np.nan,5)*pq.um
        f.curs, = f.ax.plot(
            nowhere,nowhere,
#            animated=True,
            c='b',
            lw=2,
            zorder=10,
        )
        f.ax.invert_yaxis()
        f.ax.set_xlim(*xr)
        f.ax.set_ylim(*yr[::-1])
        self._map_fig = f



    @tr.on_trait_change('map.extents')
    def _update_map_coords(self):
#        print('update map coords',self.map and self.map.extents)
        if self.map is None or self._map_fig is None:
            return
        self._map_fig.request_update()

    def _create_drift_cancel_plot(self, parent):
        f = QtFigure(
            parent,
            figsize=(1.5, 1.5), dpi=100,
            update=self._update_fb_map_image
        )
        xr,yr = self.fb_map.extents.mag_in(pq.um)
        data = self.fb_map.data.magnitude
        f.img = f.ax.pcolorfast(
            xr,yr,data,
            animated=True,
            cmap='afmhot',
        )
        f.ax.invert_yaxis()
        f.ax.xaxis.set_visible(False)
        f.ax.yaxis.set_visible(False)
        self._fb_map_fig = f
        

    def _create_rate_plot(self, parent):
        f = QtFigure(
            parent,
            figsize=(3, 1.5), dpi=100,
            xlabel='',ylabel='Counts [kHz]',
            left=0.2,bottom=0.1,
            top = 0.1, right=0.04,
            update=self._update_rate_trace
        )
        ax = f.ax
        line, = ax.plot(np.tile(np.nan,100))
        f.trace = line
        ax.set_xlim(0,100)
        ax.xaxis.set_visible(False)

        for item in (
                [ax.title, ax.xaxis.label, ax.yaxis.label]
                + ax.get_xticklabels() + ax.get_yticklabels()
        ):
            item.set_fontsize(8)

        self._rate_fig = f


    def _create_HBT_plot(self, parent):
        f = QtFigure(
            parent,
            figsize=(9, 3), dpi=100,
            xlabel=r'$\tau$ [ns]',ylabel='$g^2$',
            left=0.08,bottom=0.15,
            top = 0.04, right=0.03,
            update=self._update_HBT_plot
        )        
        ax = f.ax
        ax.axhline(1,color='r')
        ax.axhline(0.5,color='r')
        line, = ax.plot([0],[0])
        f.hist = line
        
        for item in (
                [ax.title, ax.xaxis.label, ax.yaxis.label]
                + ax.get_xticklabels() + ax.get_yticklabels()
        ):
            item.set_fontsize(8)

        self._HBT_fig = f
       
        
    @tr.on_trait_change('_s:new_hbt')
    def _HBT_updated(self, hbt):
        self.last_HBT = hbt
        self._HBT_needs_replot()
        
    @tr.on_trait_change('normalise,correct')
    def _HBT_needs_replot(self):
        if self._HBT_fig is None:
            return
        self._HBT_fig.request_update()
    
    def _update_HBT_plot(self, fig):
        hbt = self.last_HBT
        if hbt is None:
            return
        bc = hbt.bin_centres.mag_in(pq.ns)
        g2 = hbt.g2(normalise=self.normalise_hbt,correct=self.subtract_background)
        self._HBT_fig.hist.set_data(
            bc,
            g2
        )
        self._HBT_fig.ax.set_xlim(np.min(bc),np.max(bc))
        self._HBT_fig.ax.set_ylim(0,np.max(g2))


    @tr.on_trait_change('_s:_tdc:new_data')
    def _new_rate_value(self,rates):
        rate = rates.sum()
        trace = self.rate_trace
        trace[:-1] = trace[1:]
        trace[-1] = rate
        self.rate_trace = trace

    @tr.on_trait_change('rate_trace')
    def _rate_trace_change(self):
        if self._rate_fig is None:
            return
        self._rate_fig.request_update()

    @tr.on_trait_change('autoscale_rate_plot')
    def _autoscale_change(self):
        self._rate_fig.request_update()

    def _update_rate_trace(self, fig):
        new = self.rate_trace
        self._rate_fig.trace.set_ydata(new.magnitude)
        if not self.autoscale_rate_plot:
            self._rate_fig.ax.set_ylim([0, 200])
        else:
            self._rate_fig.ax.set_ylim([0, new.magnitude.max()])

    def stop_hbt(self):
        self._s.mode = 'on_target'

    def open_config(self):
        fn,g = QFileDialog.getOpenFileName(self._frame,'Open config file')
        # no idea what the second return value contains, but it always seems to be an empty string
        assert g == ''
        print('load config',fn)
        if fn:
            self.load_config(fn)
            print('done load config')

    def select_data_dir(self):
        fn,g = QFileDialog.getExistingDirectory(self._frame,'Select folder for saved data')
        # no idea what the second return value contains, but it always seems to be an empty string
        assert g == ''
        if fn:
            self.save_dir = fn

    def save_data(self):
        basepath = self.save_dir
        now = datetime.datetime.now()
        basefn = os.path.join(basepath,now.strftime('%Y%m%d-%H%M%S-'))

        hbt = self.last_HBT
        if hbt is not None:
            bc = hbt.bin_centres.mag_in(pq.ns)
            g2 = hbt.g2(normalise=self.normalise,correct=self.correct)

            np.savetxt(
                basefn + 'correlations.csv',
                np.c_[bc,g2],
                delimiter=', ',
                header = (
                    "Photon auto-correlations\n"
                    + ("normalised to 1 at long delays\n" if self.normalise else "normalised using average count rate\n")
                    + ("uncorrelated background subtracted\n" if self.correct else "")
                    + "delay [ns], g2 [unitless]"
                ),
            )

        np.savetxt(
            basefn + 'map.csv',
            self.map.data.mag_in(pq.kHz),
            delimiter = ', ',
            header = (
                "Scanning confocal microscope image, average photon count rate in [kHz]\n"
                + "Spatial resolution %.2f / %.2f um"%tuple(self.map.step.mag_in(pq.um))
            ),
        )


    @tr.on_trait_change('_map_fig:button_press_event')
    def _map_clicked(self,event):
        if event.xdata is None or event.ydata is None:
            return
        pos = (event.xdata, event.ydata) * pq.um
#        print("Mouse clicked at ", pos)
        self._s.choose_point(pos)
        # TODO: plot crosshair

    @tr.on_trait_change('map.region_updated')
    def _map_updated(self,event):
        if not self._map_fig:
            return
#        slice, update = event
 #       print('map updated')
        self._map_fig.request_update()
        
    @tr.on_trait_change('_s:fb_map.centre')
    def _fb_map_moved(self,event):
        f = self._map_fig
        c = f.curs
        m = self.fb_map
        if m is None:
            nowhere = np.tile(np.nan,5)*pq.um
            c.set_data(
                nowhere,
                nowhere
            )
        else:
            (x0,x1),(y0,y1) = m.extents
            c.set_data(
                pq.asanyarray([x0,x1,x1,x0,x0]),
                pq.asanyarray([y0,y0,y1,y1,y0])
            )
        self._map_fig.request_update()
        
    def _update_map_image(self, fig):
        data = self.map.data.magnitude
        x,y = self.map.extents
        img = fig.img
        ax = fig.ax
        img.set_data(data)
        img.set_clim(data.min(),data.max())
        img.set_extent(np.concatenate([x,y]))
#        print('update map image ',x,y,img.get_extent())
        ax.set_xlim(*x)
        ax.set_ylim(*y[::-1])
        
    @tr.on_trait_change('_s:fb_map.region_updated')
    def _fb_map_updated(self,event):
        if not self._fb_map_fig:
            return
#        slice, update = event
        self._fb_map_fig.request_update()
        
    def _update_fb_map_image(self, fig):
        data = self.fb_map.data.magnitude
        img = fig.img
        img.set_data(data)
        img.set_clim(data.min(),data.max())
        fig.ax.autoscale(None)


