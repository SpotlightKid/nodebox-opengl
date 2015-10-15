#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import division, print_function

# Add the upper directory (where the nodebox module is) to the search path.
import os, sys; sys.path.insert(0, os.path.join("..", ".."))

from nodebox.graphics import *


class ImageCanvas(Canvas):
    def __init__(self, img, *args, **kwargs):
        self.img = img
        Canvas.__init__(self, *args, **kwargs)

    def _maximize_height(self):
        self.iheight = self.height
        self.iwidth = img.width * (self.height / self.img.height)
        self.iy = 0
        self.ix = (self.width - self.iwidth) / 2

    def _maximize_width(self):
        self.iwidth = self.width
        self.iheight = img.height * (self.width / self.img.width)
        self.ix = 0
        self.iy = (self.height - self.iheight) / 2

    def on_resize(self):
        if self.width >= self.height:
            if img.width >= img.height:
                self._maximize_height()
            else:
                self._maximize_width()
        else:
            if img.width >= img.height:
                self._maximize_width()
            else:
                self._maximize_height()

    def setup(self):
        self.on_resize()

    def draw(self):
        self.clear()
        background(0.0)
        image(self.img, self.ix, self.iy, width=self.iwidth,
              height=self.iheight)


if len(sys.argv) >= 2:
    img = Image(sys.argv[1])
else:
    img = Image('creature.png')

canvas = ImageCanvas(img, 800, 600, resizable=True)
canvas.run()
