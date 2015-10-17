#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import division, print_function, unicode_literals

# Add the upper directory (where the nodebox module is) to the search path.
import os, sys; sys.path.insert(0, os.path.join("..", ".."))

from nodebox.graphics import *
from nodebox.animation.actions import Actionable, Fade, MoveToY, MoveByY
from nodebox.animation.tween import *


class DynamicText(Layer):
    def __init__(self, *args, **kwargs):
        super(DynamicText, self).__init__()
        self.x = kwargs.pop('x', 0)
        self.y = kwargs.pop('y', 0)
        self.opacity = kwargs.pop('opacity', 1.)
        self.text = Text(*args, **kwargs)
        self.width, self.height = self.text.metrics

    def draw(self):
        r, g, b = self.text.fill.rgb
        self.text.fill = color(r, g, b, self.opacity)
        self.text.draw(0, 0)


class MyCanvas(Canvas):
    def __init__(self, *args, **kwargs):
        Canvas.__init__(self, *args, **kwargs)

        self.text = DynamicText("NodeBox for OpenGL",
                                font="Times New Roman",
                                fontsize=75,
                                fontweight=BOLD,
                                lineheight=1.2,
                                fill=color(1.),
                                opacity=0.)
        self.append(self.text)

    def on_resize(self):
        self.text.x = (self.width - self.text.width) / 2

    def update(self):
        if self.frame == 1:
            self.text.do(Fade(1., 1.5, ease_in_expo))
            self.text.do(MoveByY(-self.height / 2, 3, ease_out_sine))
        elif self.frame == 270:
            self.text.do(MoveToY(-self.text.height, 1.5, ease_in_elastic_small))
        elif self.frame == 400:
            self.stop()

    def setup(self):
        self.mouse.cursor = HIDDEN
        self.text.x = (self.width - self.text.width) / 2
        self.text.y = self.height

    def draw(self):
        self.clear()
        background(0.0)


canvas = MyCanvas()
aspect = canvas.screen.width / canvas.screen.height
canvas.size = (1024, int(1024 * (1.0 / aspect)))
canvas.fullscreen = True
canvas.run()
