__author__ = 'yves'

import traits.api as tr

from ..hw.pyflycam import *

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

    def takePicture(self, name):
        if not hasattr(self, "_context"):
            self.initCamera()

        fc2StartCapture(self._context)
        # create the two pictures one for getting input the other to save
        rawImage = fc2Image()
        convertedImage = fc2Image()
        fc2CreateImage(rawImage)
        fc2CreateImage(convertedImage)

        fc2RetrieveBuffer(self._context, rawImage)
        self.savePicture(name, rawImage, convertedImage)

        fc2DestroyImage(rawImage)
        fc2DestroyImage(convertedImage)
        fc2StopCapture(self._context)

    def savePicture(self, name, rawImage, convertedImage):
        fc2ConvertImageTo(FC2_PIXEL_FORMAT_BGR, rawImage, convertedImage)

        fc2SaveImage(convertedImage, name.encode('utf-8'), 6)

    def uninitCamera(self):
        fc2StopCapture(self._context)
        fc2DestroyContext(self._context)

    def initCamera(self):
        error = fc2Error()
        self._context = fc2Context()
        self._guid = fc2PGRGuid()
        self._numCameras = c_uint()

        error = fc2CreateContext(self._context)
        if error != FC2_ERROR_OK.value:
            print("Error in fc2CreateContext: " + str(error))

        error = fc2GetNumOfCameras(self._context, self._numCameras)
        if error != FC2_ERROR_OK.value:
            print("Error in fc2GetNumOfCameras: " + str(error))
        if self._numCameras == 0:
            print("No Cameras detected")

        # get the first camera
        error = fc2GetCameraFromIndex(self._context, 0, self._guid)
        if error != FC2_ERROR_OK.value:
            print("Error in fc2GetCameraFromIndex: " + str(error))

        error = fc2Connect(self._context, self._guid)
        if error != FC2_ERROR_OK.value:
            print("Error in fc2Connect: " + str(error))
