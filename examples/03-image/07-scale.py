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

    def on_resize(self):
        self.iheight = self.img.height * (self.width / self.img.width)

        if self.iheight > self.height:
            self.iheight = self.height
            self.iwidth = self.img.width * (self.height / self.img.height)
            self.iy = 0
            self.ix = (self.width - self.iwidth) / 2
        else:
            self.iwidth = self.width
            self.ix = 0
            self.iy = (self.height - self.iheight) / 2

    def draw(self):
        self.clear()
        background(0.0)
        image(self.img, self.ix, self.iy, width=self.iwidth,
              height=self.iheight)


img = Image(sys.argv[1] if len(sys.argv) >= 2 else 'creature.png')
canvas = ImageCanvas(img, 800, 600, resizable=True)
canvas.run()
