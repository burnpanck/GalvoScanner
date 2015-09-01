__author__ = 'yves'



class FlyCam(tr.HasStrictTraits):
    # setImage properties
    def setImageProperties(self, gain=0.0, shutter=10.0):
        gainProp = fc2Property()
        shutterProp = fc2Property()
        gainProp.type = FC2_GAIN
        shutterProp.type = FC2_SHUTTER

        # retrieve current settings
        fc2GetProperty(self._context, gainProp)
        fc2GetProperty(self._context, shutterProp)

        gainProp.absValue = gain
        shutterProp.absValue = shutter

        fc2SetProperty(self._context, gainProp)
        fc2SetProperty(self._context, shutterProp)