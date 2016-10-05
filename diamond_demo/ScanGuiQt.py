import sys

from functools import partial
import time
import traceback
import importlib
import os.path
import abc
import datetime

from PyQt5.QtCore import pyqtSignal, pyqtSlot, QObject
from PyQt5.QtGui import QPalette
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QMessageBox,
    QHBoxLayout, QVBoxLayout, QGridLayout,
    QPushButton, QCheckBox, QLineEdit, QLabel, QSlider,
    QSizePolicy,
    QFileDialog,
)

import numpy as np
import quantities as pq
import traits.api as tr

import matplotlib as mpl
mpl.use('Qt5Agg')
import matplotlib.axes
import matplotlib.backends.backend_qt5agg

from yde.lib.misc.basics import Struct
from yde.lib.quantity_traits import QuantityArrayTrait
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

    button_press_event = tr.Event
    
    def __init__(self, parent, fig=dict(), ax=dict(), *, grid=None, left=0.1, right=0.1, top=0.1, bottom=0.1, **kw):
        for k in 'figsize dpi'.split():
            if k in kw:
                fig[k] = kw.pop(k)

        for k in 'xlabel ylabel'.split():
            if k in kw:
                ax[k] = kw.pop(k)
        if False:
            if grid is not None:
                bgc = parent.parent().palette().color(QPalette.Background)
            else:
                bgc = parent.palette().color(QPalette.Background)
        fig.setdefault(
            'facecolor',
#            (bgc.red()/255,bgc.green()/255,bgc.blue()/255)
            'none'
        )
        f = mpl.figure.Figure(**fig)
        ax = f.add_axes([left,bottom,1-left-right,1-bottom-top],**ax)
        canvas = mpl.backends.backend_qt5agg.FigureCanvasQTAgg(f)
        if grid is None:
            canvas.setParent(parent)
        else:
            parent.addWidget(canvas,grid['row'],grid['column'],grid['rowspan'],grid['columnspan'])
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
        self._notifier.emit()

    @pyqtSlot()
    def _do_update(self):
        if not self.update:
            return
        self.update(self)
        self.canvas.draw()

class QtTraitLink(tr.ABCHasStrictTraits):
    obj = tr.Instance(tr.HasTraits)
    trait = tr.Str
    ui = tr.Any
    auto_update = tr.Bool(True)
    _notifier = tr.Instance(Signal)

    ui_changed = tr.Event(desc="emitted when the UI changes, which might not yet have been reflected on the trait")

    @classmethod
    def make(cls,parent,obj,trait,*,row=None,column=None,**kw):
        t = trait_type(obj, trait)
        if cls is QtTraitLink:
            # determine subclass from type
            if isinstance(t, tr.Bool):
                cls = QtBoolLk
            elif isinstance(t, QuantityArrayTrait):
                cls = QtQuantityLk
            else:
                cls = QtFloatLk
        traits = dict()
        for k in cls.class_editable_traits():
            if k in kw:
                traits[k] = kw.pop(k)
        sig = Signal()
        ret = cls(obj=obj,trait=trait,_notifier=sig,**traits)
        ret._make_ui(**kw)
        if row is None or column is None:
            ret.ui.setParent(parent)
        else:
            parent.addWidget(ret.ui,row,column)
        obj.on_trait_change(
            ret._request_update,
            ret.trait
        )
        sig.connect(ret._do_update)
        ret._set(getattr(obj,trait))
        return ret
    
     
    def _request_update(self):
        self._notifier.emit()
     
    @pyqtSlot()
    def _do_update(self):
        new = getattr(self.obj, self.trait)
        print('update gui ',self.trait,new)
        self._set(new)
    
    def _update_trait(self, *args, **kw):
        try:
            new = self._get()
        except Exception:
            return
        self.ui_changed = new
        if not self.auto_update:
            return
#        print('_update traits')
        print('update trait ',self.trait,args,kw,new)
        setattr(self.obj, self.trait, new)

    @abc.abstractmethod
    def _make_ui(self,**ui): pass
    
    @abc.abstractmethod
    def _set(self, val): pass
    
    @abc.abstractmethod
    def _get(self): pass

class QtBoolLk(QtTraitLink):
    auto_update = True
    def _make_ui(self,**ui):
        self.ui = QCheckBox(**ui)
        self.ui.stateChanged.connect(self._update_trait)
    def _set(self, val):
        self.ui.setChecked(val)
    def _get(self):
        return self.ui.isChecked()

class QtStrLk(QtTraitLink):
    readonly = tr.Bool(False)

    def _make_ui(self, **ui):
        if self.readonly:
            self.ui = QLabel(**ui)
        else:
            self.ui = QLineEdit(**ui)
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


class QtFloatLk(QtStrLk):
    fmt = tr.Str('%.3f')

    def _fmt(self, val):
        return self.fmt%val
    def _parse(self, val):
        return float(val)
        
class QtQuantityLk(QtFloatLk):
    unit = tr.Any
    
    def _fmt(self, val):
        return self.fmt%val.mag_in(self.unit) + ' '+ str(self.unit.dimensionality)
    def _parse(self, val):
        parts = val.split(None,1)
        if len(parts)>1:
            unit = getattr(pq,parts[1])
        else:
            unit = self.unit
        return float(parts[0]) * unit
        
class ScanGui(tr.HasTraits):
    _s = tr.Instance(ScanningRFMeasurement)
    _frame = tr.Instance(QWidget)
    _tk_objects = tr.Dict(tr.Str,tr.Any)
    _map_fig = tr.Instance(QtFigure)
    _fb_map_fig = tr.Instance(QtFigure)
    _rate_fig = tr.Instance(QtFigure)
    _HBT_fig = tr.Instance(QtFigure)

    focus = tr.DelegatesTo('_s')
    mode = tr.DelegatesTo('_s')
    position = tr.DelegatesTo('_s')
    signal_ratio = tr.DelegatesTo('_s')
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

    @classmethod
    @catch2messagebox
    def main(cls,**kw):
        try:
            tr.push_exception_handler(
                handle_traits_error,
                reraise_exceptions=False,
                main=True
            )
            print('A')
            app = QApplication([])
            print('B')
            self = cls(**kw)
            print('C')
            ec = app.exec_()
            print('D',ec)
            self.deinit()
        finally:
            tr.pop_exception_handler()
        return ec

    def deinit(self):
        self._s.deinit()

    @classmethod
    def _handle_cfg(cls, obj, settings):
        for k,v in settings.items():
            t = declared_trait(obj.trait(k))
            if isinstance(t,tr.Instance):
                cls._handle_cfg(getattr(obj, k), v)
                continue
            if (isinstance(t,QuantityArrayTrait) or isinstance(t,tr.DelegatesTo)) and isinstance(v,str):
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


    def _create_frame(self):

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

        s.rcQuTau = make_button("Reconnect QuPsi",1,1,self._s._tdc.reset)

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


        if False:
            s.dataDirVar = Tk.StringVar()
            s.dataDirEntry = Tk.Entry(frame, textvariable=s.dataDirVar)
            s.dataDirEntry.grid(row=5, column=7)

            s.selectDataDir = Tk.Button(
                frame, text="Select",
                command = cb(lambda:self.select_data_dir(s.dataDirVar))
            )
            s.selectDataDir.grid(row=5, column=8)

            s.saveData = Tk.Button(
                frame, text="Save data",
                command = cb(lambda:self.save_data(s.dataDirVar.get()))
            )
            s.saveData.grid(row=6, column=7)

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

            # force hbt
            s.hbt_force_var = Tk.BooleanVar()
            s.hbt_force = Tk.Checkbutton(
                frame, text="Force HBT",
                variable=s.hbt_force_var,
                command=cb(lambda:self.trait_set(hbt_force=s.hbt_force_var.get()))
            )
            s.hbt_force.grid(row=6, column=8)


            # scanner mode
            s.modeVar = Tk.StringVar()
            self.on_trait_change(
                lambda mode: s.modeVar.set(mode),
                'mode'
            )
            self.trait_property_changed('mode',self.mode)
            s.modeLbl = Tk.Label(frame, textvariable=s.modeVar)
            s.modeLbl.grid(row=4, column=7)

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
        self._create_feedback_plot(grid)
        self._create_HBT_plot(grid)

        self._frame = wnd
        wnd.show()


    def _create_scan_plot(self, grid):
        f = QtFigure(
            grid,
            figsize=(4, 4), dpi=100,
            xlabel='',ylabel='',
            left=0.12,bottom=0.07,
            top = 0.04, right=0.04,
            update=self._update_map_image,
            grid = dict(row=4,column=0,rowspan=4,columnspan=2),
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

    def _create_feedback_plot(self, grid):
        f = QtFigure(
            grid,
            figsize=(1.5, 1.5), dpi=100,
            grid=dict(row=4,column=2,columnspan=2,rowspan=3),
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
        

    def _create_rate_plot(self, grid):
        f = QtFigure(
            grid,
            figsize=(3, 1.5), dpi=100,
            xlabel='',ylabel='Counts [kHz]',
            left=0.2,bottom=0.1,
            top = 0.1, right=0.04,
            grid=dict(row=4,column=4,columnspan=3,rowspan=3),
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


    def _create_HBT_plot(self, grid):
        f = QtFigure(
            grid,
            figsize=(9, 3), dpi=100,
            xlabel=r'$\tau$ [ns]',ylabel='$g^2$',
            left=0.08,bottom=0.15,
            top = 0.04, right=0.03,
            grid=dict(row=7,column=2,columnspan=7,rowspan=1),
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
    
    def _update_HBT_plot(self, event):
        hbt = self.last_HBT
        if hbt is None:
            return
        bc = hbt.bin_centres.mag_in(pq.ns)
        g2 = hbt.g2(normalise=self.normalise,correct=self.correct)
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

    def _rate_trace_changed(self):
        if self._rate_fig is None:
            return
        self._rate_fig.request_update()

    def _update_rate_trace(self, event):
        new = self.rate_trace
        self._rate_fig.trace.set_ydata(new.magnitude)
        if not self.autoscale:
            self._rate_fig.ax.set_ylim([0, 200])
        else:
            self._rate_fig.ax.set_ylim([0, new.magnitude.max()])

    def reset_hbt(self, reso, range):
        self._s.setup_hbt(reso,range)

    def stop_hbt(self):
        self._s.mode = 'on_target'

    def show_galvo_voltages(self):
        messagebox.showinfo("Galvo voltages", "Phi: %s V, Theta: %s V" % tuple(
            self._s._pos.galvo_voltage.mag_in(pq.V)
        ))

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


