__author__ = 'yves'


class TDC(tr.HasStrictTraits):
    def init(self):
        # accept any device
        TDC_init(-1)
        # enable all channels
        TDC_enableChannels(0xff)
        # enable hbt
        TDC_enableHbt(True)
        # enable start stop
        TDC_enableStartStop(True)
        # exposure time in ms
        self.exposureTime = 1
        TDC_setExposureTime(self.exposureTime)
        TDC_clearAllHistograms()
        # the calibration values, read them from the config file