# -*- coding: utf-8 -*-

"""
Yves Delley
"""

import sys

import numpy as np

from PyQt5.QtWidgets import (QWidget, QSlider, QApplication,
                             QHBoxLayout, QVBoxLayout)
from PyQt5.QtCore import QObject, Qt, pyqtSignal, QPointF, QRectF
from PyQt5.QtGui import QPainter, QColor, QPen


class AlignmentWidget(QWidget):
    def __init__(self,*args,**kw):
        super().__init__(*args,**kw)

        self.initUI()

    def initUI(self):

        self.setMinimumSize(64, 64)

        self.image = None
        self.last_image = None
        # all coordinates refer to the same coordinate system (except scale)
        self.imgcentre = np.r_[0,0]    # position of image centre
        self.imgreso = 1          # pixel size

        self.centre = np.r_[0,0]
        self.scale = 1     # the ratio between image pixels to displayed pixels

        self.cursor = np.r_[0,0]

        self.cursor_size = 5


    def paintEvent(self, e):

        qp = QPainter()
        qp.begin(self)
        self.drawWidget(qp)
        qp.end()

    def drawWidget(self, qp):

        scale = self.scale
        wsize = self.size()
        wsize = np.r_[wsize.width(),wsize.height()]
        orig = self.centre - wsize/(2*scale) # coordinates of pixel 0,0


        img = self.image
        if img is None:
            self.last_image = img
            return
        isize = img.size()
        isize = self.imgreso*np.r_[isize.width(),isize.height()]

        # image corners in widget pixels
        topleft = (self.imgcentre - 0.5*isize - orig)*scale

        qp.drawImage(
            QRectF(*np.r_[topleft,isize*scale]),
            img
        )

        pen = QPen(QColor(120, 0, 0), 1,
                   Qt.SolidLine)

        qp.setPen(pen)
        qp.setBrush(Qt.NoBrush)
        qp.drawEllipse(QPointF(
            *(self.cursor-orig)*scale
        ), self.cursor_size, self.cursor_size)

        self.last_image = img
