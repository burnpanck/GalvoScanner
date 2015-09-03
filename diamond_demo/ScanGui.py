import sys

from functools import partial
import time
import traceback
import importlib

# conditional module loading python 2/3
try:
    import tkinter as Tk
    import tkinter.messagebox as messagebox, tkinter.filedialog as filedialog
except ImportError:
    import Tkinter as Tk
    import tkMessageBox as messagebox, tkFileDialog as filedialog

import numpy as np
import quantities as pq
import traits.api as tr

from .lib import Events
from .Scanner import ScanningRFMeasurement, FluorescenceMap

from yde.lib.misc.basics import Struct
from yde.lib.quantity_traits import QuantityArrayTrait

def catch2messagebox(fun):
    """ wrap function to display a message when an exception happens
    """
    def wrapper(*args,**kw):
        try:
            fun(*args,**kw)
        except Exception as ex:
#            raise
            messagebox.showerror(
                "Exception: "+str(ex),
                ''.join(traceback.format_exc())
            )
            raise
    return wrapper

def handle_traits_error(object, trait_name, old_value, new_value):
    messagebox.showerror(
        'TraitsError',
        'Failed to set trait "%s" of %s object to %s (was %s):\n'%(
            trait_name, type(object).__name__, new_value, old_value
        )+''.join(traceback.format_exc())
    )
    raise

class ScanGui(tr.HasTraits):
    _s = tr.Instance(ScanningRFMeasurement)
    _frame = tr.Instance(Tk.Frame)
    _tk_objects = tr.Dict(tr.Str,tr.Any)
    _map_image = tr.Any(desc='matplotlib image')
    _map_canvas = tr.Any(desc='matplotlib tkagg canvas')
    _rate_plot = tr.Any(desc='matplotlib line')
    _rate_ax = tr.Any(desc='matplotlib axes')
    _rate_canvas = tr.Any(desc='matplotlib tkagg canvas')
    _HBT_plot = tr.Any(desc='matplotlib line')
    _HBT_ax = tr.Any(desc='matplotlib axes')
    _HBT_canvas = tr.Any(desc='matplotlib tkagg canvas')

    focus = tr.DelegatesTo('_s')
    position = tr.DelegatesTo('_s')
    background_rate = tr.DelegatesTo('_s')
    auto_optimisation = tr.DelegatesTo('_s')
    autoscale = tr.Bool(True)
    normalise = tr.Bool(True)
    correct = tr.Bool(True)
    map = tr.Instance(FluorescenceMap,kw=dict(
        shape = (10,10),
        step = (0.5,0.5)*pq.um,
    ))
    rate_trace = QuantityArrayTrait(np.zeros(100)*pq.kHz,shape=(None,))

    @classmethod
    @catch2messagebox
    def main(cls,**kw):
        try:
            tr.push_exception_handler(
                handle_traits_error,
                reraise_exceptions=False,
                main=True
            )
            master = Tk.Tk()
            self = cls(master, **kw)
            master.mainloop()
            self.deinit()
        finally:
            tr.pop_exception_handler()

    def deinit(self):
        self._s.deinit()

    @staticmethod
    def _config_hook(dct):
        if "_eval_" in dct:
            ctxt = dict()
            if "libraries" in dct:
                for lib in dct["libraries"]:
                    lib = str(lib)
                    ctxt[lib] = importlib.import_module(lib)
            return eval(dct["expression"],ctxt,ctxt)
        return dct

    def load_config(self, configFile):
        import json

        cfg = json.loads(open(configFile).read(), object_hook=self._config_hook)
        imports = cfg.pop("imports",[])
        settings = cfg.pop('settings',{})
        for cfgfile in imports:
            cfg.update(self.load_config(cfgfile))
        for key,value in settings.items():
            setattr(self, key, value)
        return cfg

    def __init__(self, master, config_file=None, **kw):
        scanner_kw = dict()
        for k in ''.split():
            v = kw.pop(k,None)
            if v is not None:
                scanner_kw[k] = v
        super(ScanGui,self).__init__(**kw)
        self._s = ScanningRFMeasurement(**scanner_kw)
        if config_file is not None:
            self.load_config(config_file)
        self._create_frame(master)

    def _create_frame(self, master):

        # add our gui to the master Widget
        frame = Tk.Frame(master)
        frame.pack()

        s = Struct()
        cb = catch2messagebox

        # we need one slider for focus
        # self.scaleLabel = Label(frame, text="Focus: ")
        # self.scaleLabel.grid(row=0, column=0)
        s.focusVar = Tk.StringVar()
        s.focusEntry = Tk.Entry(frame, textvariable=s.focusVar)
        s.focusEntry.grid(row=0, column=0)
        self.on_trait_change(
            lambda: s.focusEntry.event_generate('<<update>>', when='tail'),
            'focus',
        )
        self.trait_property_changed('focus',self.focus)
        s.focusEntry.bind(
            "<<update>>",
            lambda: s.focusVar.set(str(self.focus.mag_in(pq.V))),
        )
        s.focus = Tk.Button(
            frame, text="Set Focus",
            command=cb(lambda: self.trait_set(focus=float(s.focusVar.get())*pq.V))
        )
        s.focus.grid(row=0, column=1)

        # reconnectQuTau
        s.rcQuTau = Tk.Button(
            frame, text="Reconnect QuTau",
            command=cb(lambda:self._s._tdc.reset)
        )
        s.rcQuTau.grid(row=1, column=1)
        # self.scale = Scale(frame,from_=0, to=5, resolution=0.001, orient=HORIZONTAL, command=self.ValueChanged)
        # self.scale.grid(row=0,column=1)
        # a checkbox for switching autoscale off or on
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

        # add button to stop scanning
        s.stopScan = Tk.Button(
            frame, text="Stop Scan",
            command = cb(self._s.stop)
        )
        s.stopScan.grid(row=2, column=1)

        # button for saving the state
        s.saveState = Tk.Button(frame, text="Save state", command=cb(self.save_state))
        s.saveState.grid(row=3, column=2)
        # button for taking a picture with the ccd
        s.ccdPic = Tk.Button(frame, text="Take Picture", command=cb(self.take_picture))
        s.ccdPic.grid(row=3, column=3)
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
        s.hbtStopButton = Tk.Button(frame, text="Clear HBT", command=cb(self.hideHBT))
        s.hbtStopButton.grid(row=1, column=6)
        s.hbtUnRunButton = Tk.Button(frame, text="Stop HBT", command=cb(self.stop_hbt))
        s.hbtUnRunButton.grid(row=1, column=7)
        # checkbox for correction of HBT
        s.correctionVar = Tk.BooleanVar()
        s.correctionCheck = Tk.Checkbutton(
            frame, text="Correction", variable=s.correctionVar,
            command=cb(lambda:self.enable_correction(
                s.correctionVar.get(),
                float(s.bgrateVar.get())*pq.kHz,
            )),
        )
        s.correctionCheck.grid(row=3, column=6)
        s.bgrateVar = Tk.StringVar()
        s.bgrateEntry = Tk.Entry(frame, textvariable=s.bgrateVar)
        s.bgrateEntry.grid(row=3, column=7)
        self.on_trait_change(
            lambda rate: s.bgrateVar.set(str(rate.mag_in(pq.kHz))),
            'background_rate'
        )
        self.trait_property_changed('background_rate',self.background_rate)

        # autocorrection
        s.autocorrVar = Tk.BooleanVar()
        s.autocorrCheck = Tk.Checkbutton(
            frame, text="autocorrection", variable=s.autocorrVar,
            command=cb(lambda:self.enable_autocorr(s.autocorrVar.get())),
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
            command=cb(lambda:self._s.trait_set(normalise=s.normVar.get())),
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
        s.autofeedbackCheck.select()

        # entry fields for binWidth and binCount
        s.binWidth = Tk.StringVar()
        s.binCount = Tk.StringVar()
        s.widthlabel = Tk.Label(frame, text="Time Resolution")
        s.countLabel = Tk.Label(frame, text="range")
        s.widthEntry = Tk.Entry(frame, textvariable=s.binWidth)
        s.countEntry = Tk.Entry(frame, textvariable=s.binCount)
        s.binCount.set("20")
        s.binWidth.set("1")
        s.widthlabel.grid(row=0, column=3)
        s.widthEntry.grid(row=0, column=4)
        s.countLabel.grid(row=1, column=3)
        s.countEntry.grid(row=1, column=4)

        self._create_scan_plot(frame)
        self._create_rate_plot(frame)
        self._create_HBT_plot(frame)

        frame.config()

        self._frame = frame

    def _create_scan_plot(self, frame):
        from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
        from matplotlib.figure import Figure

        f = Figure(figsize=(4, 4), dpi=100)
        f.subplots_adjust(left=0.2)
        ax = f.add_subplot(111)
        xr,yr = self.map.extents.mag_in(pq.um)
        img = ax.pcolorfast(
            xr,yr,self.map.data.magnitude,
            animated=True,
            cmap='CMRmap',
        )

        toolbar_frame = Tk.Frame(frame)
        toolbar_frame.grid(row=4, column=0, columnspan=2, rowspan=6)

        canvas = FigureCanvasTkAgg(f, master=toolbar_frame)
        canvas.show()
        canvas_widget = canvas.get_tk_widget()
        canvas_widget.pack(side=Tk.BOTTOM, fill=Tk.BOTH, expand=True)
        canvas.mpl_connect('button_press_event', self._map_clicked)

        if False:
            from matplotlib.backends.backend_tkagg import NavigationToolbar2TkAgg
            return NavigationToolbar2TkAgg(canvas, master)

        self._map_image = img
        self._map_canvas = canvas


    def _create_rate_plot(self, frame):
        from matplotlib.figure import Figure
        from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

        f = Figure(figsize=(3, 1.5), dpi=100)
        f.subplots_adjust(left=0.2)
        ax = f.add_subplot(111)

        line, = ax.plot(np.tile(np.nan,100))
        ax.set_xlim(0,100)


        for item in (
                [ax.title, ax.xaxis.label, ax.yaxis.label]
                + ax.get_xticklabels() + ax.get_yticklabels()
        ):
            item.set_fontsize(8)


        toolbar_frame = Tk.Frame(frame)
        toolbar_frame.grid(row=4, column=4, columnspan=3, rowspan=3)

        canvas = FigureCanvasTkAgg(f, master=toolbar_frame)
        canvas.show()
        canvas_widget = canvas.get_tk_widget()
        canvas_widget.pack(side=Tk.BOTTOM, fill=Tk.BOTH, expand=True)

        self._rate_plot = line
        self._rate_ax = ax
        self._rate_canvas = canvas

        frame.bind('<<rate_trace>>',self._update_rate_trace)


    def _create_HBT_plot(self, frame):
        from matplotlib.figure import Figure
        from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

        f = Figure(figsize=(9, 3), dpi=100)
        f.subplots_adjust(left=0.2)
        ax = f.add_subplot(111)

        ax.axhline(1,color='r')
        ax.axhline(0.5,color='r')
        line, = ax.plot([0],[0])

        for item in (
                [ax.title, ax.xaxis.label, ax.yaxis.label]
                + ax.get_xticklabels() + ax.get_yticklabels()
        ):
            item.set_fontsize(8)


        toolbar_frame = Tk.Frame(frame)
        toolbar_frame.grid(row=7, column=2, columnspan=7, rowspan=3)

        canvas = FigureCanvasTkAgg(f, master=toolbar_frame)
        canvas.show()
        canvas_widget = canvas.get_tk_widget()
        canvas_widget.pack(side=Tk.BOTTOM, fill=Tk.BOTH, expand=True)

        self._HBT_plot = line
        self._HBT_ax = ax
        self._HBT_canvas = canvas

    @tr.on_trait_change('_s:new_hbt')
    def _HBT_updated(self, hbt):
        self._HBT_plot.set_data(
            hbt.bin_centres.mag_in(pq.ns),
            hbt.g2(normalise=self.normalise,correct=self.correct)
        )
#        self._HBT_canvas.draw()


    @tr.on_trait_change('_s:_tdc:new_data')
    def _new_rate_value(self,rates):
        print('new rate data')
        rate = rates.sum()
        trace = self.rate_trace
        trace[:-1] = trace[1:]
        trace[-1] = rate
        print('update trace data')
        self.rate_trace = trace
        print('update trace data done')

    def _rate_trace_changed(self):
        print('rate_trace_Changed')
        self._frame.event_generate('<<rate_trace>>',when='tail')
        print('rate_trace_Changed done')
    def _update_rate_trace(self):
        print('updating plot on-screen')
        new = self.rate_trace
        self._rate_plot.set_ydata(new.magnitude)
        if not self.autoscale:
            self._rate_ax.set_ylim([0, 200])
        else:
            self._rate_ax.set_ylim([0, new.magnitude.max()])
        self._rate_canvas.draw()

    def reset_hbt(self, reso, range):
        self._s.setup_hbt(reso,range)

    def hideHBT(self):
        raise NotImplementedError
        self.gs.hbtRunning = False

    def stop_hbt(self):
        self._s.mode = 'on_target'

    def show_galvo_voltages(self):
        messagebox.showinfo("Galvo voltages", "Phi: %s V, Theta: %s V" % tuple(
            self._s._pos.galvo_voltage.mag_in(pq.V)
        ))

    def enable_correction(self,enable,background_rate):
        if enable:
            self.background_rate = background_rate
            self.gs.signalCorrection = True
        else:
            self.gs.signalCorrection = False

    def enable_autocorr(self,enable):
        if not enable:
            self.gs.autocorrection = False
            self.correctionTextField.config(state="normal")
        else:
            self.gs.autocorrection = True
            self.correctionTextField.config(state="readonly")

    def save_state(self):
        raise NotImplementedError
        f = filedialog.asksaveasfilename(filetypes=[("Numpy Binary", "*.npy")])
        if f:
            self.gs.saveState(f)

    def take_picture(self):
        raise NotImplementedError
        f = filedialog.asksaveasfilename(filetypes=[("PNG", "*.png")], defaultextension=".png")
        if f:
            self.gs.takePicture(f)

    def open_config(self):
        f = filedialog.askopenfile(initialdir="./configs", filetypes=[("ConfigFile", "*.cfg")])
        if f is not None:
            self.load_config(f.name)


    def _map_clicked(self,event):
        pos = np.r_[event.xdata, event.ydata] * pq.um
        print("Mouse clicked at ", pos)
        self._s.choose_point(pos)
        # TODO: plot crosshair

    @tr.on_trait_change('map:region_updated')
    def _map_updated(self,event):
        slice, update = event
        data = self.data.magnitude
        self._map_image.set_data(data)
        self._map_image.set_clim(data.min(),data.max())
#        self._map_canvas.draw()


