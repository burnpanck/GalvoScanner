import sys

from functools import partial
import time
import traceback
import importlib
import os.path
import abc
import datetime

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QMessageBox,
    QHBoxLayout, QVBoxLayout, QGridLayout,
    QPushButton, QLineEdit, QLabel, QSlider,
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

class QtFigure(tr.HasTraits):
    frame = tr.Any
    ax = tr.Instance(mpl.axes.Axes)
    canvas = tr.Instance(mpl.backends.backend_qt5agg.FigureCanvasQTAgg)
    update = tr.Callable

    button_press_event = tr.Event
    
    def __init__(self, parent, fig=dict(), ax=dict(), *, grid=None, left=0.1, right=0.1, top=0.1, bottom=0.1, **kw):
        for k in 'figsize dpi'.split():
            if k in kw:
                fig[k] = kw.pop(k)

        for k in 'xlabel ylabel'.split():
            if k in kw:
                ax[k] = kw.pop(k)
                
        f = mpl.figure.Figure(**fig)
        ax = f.add_axes([left,bottom,1-left-right,1-bottom-top],**ax)
        return
        frame = Tk.Frame(parent)
        if grid is not None:
            frame.grid(**grid)

        canvas = mpl.backends.backend_tkagg.FigureCanvasTkAgg(f, master=frame)
        canvas.show()
        canvas_widget = canvas.get_tk_widget()
        canvas_widget.pack(side=Tk.BOTTOM, fill=Tk.BOTH, expand=True)
        def connect(e,canvas,obj):
            canvas.mpl_connect(e, lambda v: setattr(obj,e,v))
        for e in 'button_press_event'.split():
            connect(e,canvas,self)

        kw.update(
            frame = frame,
            ax = ax,
            canvas = canvas,
        )
         
        super(TkFigure, self).__init__(**kw)

        frame.bind('<<reqest_update>>',self._do_update)
        
    def request_update(self):
        self.frame.event_generate('<<reqest_update>>',when='tail')
       
    def _do_update(self, event):
        if not self.update:
            return
        self.update(self)
        self.canvas.draw()

class QtVarLink(tr.ABCHasStrictTraits):
    obj = tr.Instance(tr.HasTraits)
    trait = tr.Str
    var = tr.Any
    ui = tr.Any
    auto_update = tr.Bool(True)
    
    @classmethod
    def make(cls,parent,obj,trait,*,row=None,column=None,**kw):
        t = trait_type(obj, trait)
        if isinstance(t, tr.Bool):
            cls = TkBoolLk
        elif isinstance(t, QuantityArrayTrait):
            cls = TkQuantityLk
        else:
            cls = TkFloatLk
        traits = dict()
        for k in cls.class_editable_traits():
            if k in kw:
                traits[k] = kw.pop(k)
        ret = cls(obj=obj,trait=trait,**traits)
        ret._make_ui(parent,**kw)
        obj.on_trait_change(
            ret._request_update,
            ret.trait
        )
        ret.ui.bind('<<update_value>>',ret._update_tk)
        if ret.auto_update and False:
            ret.var.trace('w', ret._update_trait)
        ret.ui.grid(row=row,column=column)
        ret._request_update()
        return ret
    
     
    def _request_update(self):
        self.ui.event_generate('<<update_value>>',when='tail')
     
    def _update_tk(self, event):
        new = getattr(self.obj, self.trait)
        print('update tk ',self.trait,event,new)
        self.var.set(self._fmt(new))
    
    def _update_trait(self, *args, **kw):
#        print('_update traits')
        new = self._parse(self.var.get())
        print('update trait ',self.trait,args,kw,new)
        setattr(self.obj, self.trait, new)

    @abc.abstractmethod
    def _make_ui(self,parent,**ui): pass
    
    @abc.abstractmethod
    def _fmt(self, val): pass
    
    @abc.abstractmethod
    def _parse(self, val): pass

class QtBoolLk(QtVarLink):
    def _make_ui(self,parent,**ui):
        self.ui = Tk.Checkbutton(parent,variable=self.var,**ui)
    def _fmt(self, val):
        return val
    def _parse(self, val):
        return val
            
class QtFloatLk(QtVarLink):
    fmt = tr.Str('%.3f')

    def _make_ui(self,parent,**ui):
        self.ui = Tk.Entry(parent,textvariable=self.var,**ui)
    def _fmt(self, val):
        return self.fmt%val
    def _parse(self, val):
        return float(val)
        
class QtQuantityLk(QtFloatLk):
    unit = tr.Any
    
    def _fmt(self, val):
        return self.fmt%val.mag_in(self.unit) + ' '+ str(self.unit)
    def _parse(self, val):
        parts = val.split(None,1)
        if len(parts)>1:
            unit = getattr(pq,parts[1:])
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
        wnd.statusBar()

        widget = QWidget()
        wnd.setCentralWidget(widget)
        widget.setWindowTitle('ConfocalScan')

        s = Struct()
        cb = catch2messagebox

        grid = QGridLayout(widget)

        # we need one slider for focus
        # self.scaleLabel = Label(frame, text="Focus: ")
        # self.scaleLabel.grid(row=0, column=0)
        s.focus = QLineEdit()
        grid.addWidget(s.focus,0,0)
        self.on_trait_change(
            lambda v: s.focus.setText('%.2f'%v.mag_in(pq.V)),
            'focus',
        )
        s.focus.textChanged[str].connect(
            lambda v: self.trait_set(focus=float(v)*pq.V),
        )
#        self.trait_property_changed('focus',self.focus)

        s.focusSet = QPushButton()
        grid.addWidget(s.focusSet,0,1)
        s.focusSet.setText("Set Focus")
        s.focusSet.clicked[bool].connect(
            lambda: self.trait_set(focus=float(s.focus.getText())*pq.V)
        )

        # reconnectQuTau
        def reconnect():
            print('reconnect pressed!')
            self._s._tdc.reset()
        s.rcQuTau = QPushButton()
        grid.addWidget(s.rcQuTau,1,1)
        s.rcQuTau.setText("Reconnect QuTau")
        s.rcQuTau.clicked[bool].connect(reconnect)

        # self.scale = Scale(frame,from_=0, to=5, resolution=0.001, orient=HORIZONTAL, command=self.ValueChanged)
        # self.scale.grid(row=0,column=1)
        # a checkbox for switching autoscale off or on
        if False:
            s.autoscaleVar = Tk.BooleanVar()
            s.autoscale = Tk.Checkbutton(
                frame, text="Autoscale",
                variable=s.autoscaleVar,
                command=cb(lambda:self.trait_set(autoscale=s.autoscaleVar.get()))
            )
            s.autoscale.select()
            s.autoscale.grid(row=3, column=5)
            # add a button to loadConfig
            s.openConfig = Tk.Button(
                frame, text="Open Config File",
                command = cb(self.open_config)
            )
            s.openConfig.grid(row=1, column=0)

            # add a button to start the scanning
            s.startScan = Tk.Button(
                frame, text="Start Scan",
                command=cb(lambda: self._s.scan(self.map))
            )
            s.startScan.grid(row=2, column=0)

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



            # add button to stop scanning
            s.stopScan = Tk.Button(
                frame, text="Stop Scan",
                command = cb(self._s.stop)
            )
            s.stopScan.grid(row=2, column=1)

            # button for resetting position
            s.resetPos = Tk.Button(
                frame, text="Goto 0/0",
                command=cb(lambda:self._s.trait_set(position=(0,0)*pq.um)),
            )
            s.resetPos.grid(row=3, column=4)

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
            # button for showing hbt
            s.hbtButton = Tk.Button(
                frame, text="Reset HBT",
                command=cb(lambda:self.reset_hbt(
                    float(s.binWidth.get())*pq.ns,
                    float(s.binCount.get())*pq.ns,
                )),
            )
            s.hbtButton.grid(row=1, column=5)
            s.hbtUnRunButton = Tk.Button(frame, text="Stop HBT", command=cb(self.stop_hbt))
            s.hbtUnRunButton.grid(row=1, column=7)

            # force hbt
            s.hbt_force_var = Tk.BooleanVar()
            s.hbt_force = Tk.Checkbutton(
                frame, text="Force HBT",
                variable=s.hbt_force_var,
                command=cb(lambda:self.trait_set(hbt_force=s.hbt_force_var.get()))
            )
            s.hbt_force.grid(row=6, column=8)


            # checkbox for correction of HBT
            s.correctionVar = Tk.BooleanVar()
            self.on_trait_change(
                lambda n: s.correctionVar.set(n),
                'correct'
            )
            self.trait_property_changed('correct',self.correct)
            s.correctionCheck = Tk.Checkbutton(
                frame, text="correction", variable=s.correctionVar,
                command=cb(lambda:self.trait_set(correct=s.correctionVar.get())),
            )
            s.correctionCheck.grid(row=3, column=6)
            s.bgrateVar = TkVarLink.make(
                frame,
                self, 'signal_ratio',
                row=3,column=7,
                fmt = '%.3f',
            )

            # autocorrection
            s.autocorrVar = Tk.BooleanVar()
            self._s.on_trait_change(
                lambda n: s.autocorrVar.set(n),
                'auto_correction'
            )
            self._s.trait_property_changed('auto_correction',self._s.auto_correction)
            s.autocorrCheck = Tk.Checkbutton(
                frame, text="autocorrection", variable=s.autocorrVar,
                command=cb(lambda:self._s.trait_set(auto_correction=s.autocorrVar.get())),
            )
            s.autocorrCheck.grid(row=2, column=8)
            # checkbox for normalization
            s.normVar = Tk.BooleanVar()
            self.on_trait_change(
                lambda n: s.normVar.set(n),
                'normalise'
            )
            self.trait_property_changed('normalise',self.normalise)
            s.normCheck = Tk.Checkbutton(
                frame, text="Normalization", variable=s.normVar,
                command=cb(lambda:self.trait_set(normalise=s.normVar.get())),
            )
            s.normCheck.grid(row=3, column=8)

            # checkbox for automatical maximum feedback
            s.autofeedbackVar = Tk.BooleanVar()
            self.on_trait_change(
                lambda n: s.autofeedbackVar.set(n),
                'auto_optimisation'
            )
            self.trait_property_changed('auto_optimisation',self.auto_optimisation)
            s.autofeedbackCheck = Tk.Checkbutton(
                frame, text="Auto feedback", variable=s.autofeedbackVar,
                command=cb(lambda:self._s.trait_set(auto_optimisation=s.autofeedbackVar.get())),
            )
            s.autofeedbackCheck.grid(row=4, column=8)

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


            self._create_scan_plot(frame)
            self._create_feedback_plot(frame)
            self._create_rate_plot(frame)
            self._create_HBT_plot(frame)

            frame.config()

        self._frame = wnd
        wnd.show()


    def _create_scan_plot(self, frame):
        f = TkFigure(
            frame,
            figsize=(4, 4), dpi=100,
            xlabel='',ylabel='',
            left=0.12,bottom=0.07,
            top = 0.04, right=0.04,
            grid=dict(row=4,column=0,columnspan=2,rowspan=6),
            update=self._update_map_image
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

    def _create_feedback_plot(self, frame):
        f = TkFigure(
            frame,
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
        

    def _create_rate_plot(self, frame):
        f = TkFigure(
            frame,
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


    def _create_HBT_plot(self, frame):
        f = TkFigure(
            frame,
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
        f = filedialog.askopenfile(initialdir="./configs", filetypes=[("ConfigFile", "*.cfg")])
        print('load config',f.name)
        if f is not None:
            self.load_config(f.name)
            print('done load config')

    def select_data_dir(self,tkvar):
        f = filedialog.askdirectory(
            mustexist=True,
            title="Select folder where data is saved to",
        )
        if f is not None:
            tkvar.set(os.path.abspath(f))

    def save_data(self,basepath):
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
                    + ("normalised to 1 at long delays\n" if self.normalise else "normalised using average count rate")
                    + ("uncorrelated background subtracted\n" if self.correct else "")
                    + "\ndelay [ns], g2 [unitless]"
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


