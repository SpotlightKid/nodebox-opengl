#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import division, print_function, unicode_literals

# Add the upper directory (where the nodebox module is) to the search path.
import os, sys; sys.path.insert(0, os.path.join("..", ".."))

from nodebox.graphics import *
from nodebox.animation.actions import (Actionable, Delay, Fade, MoveToY,
    MoveByY, ParallelAction, SequenceAction)
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
            self.text.do(
                SequenceAction(
                    ParallelAction(
                        Fade(1., 1.5, ease_in_expo),
                        MoveToY((self.height - self.text.height) / 2, 1.5,
                                 ease_in_expo)),
                    Delay(2.),
                    MoveByY(300, 1., ease_out_sine),
                    MoveToY(-self.text.height, 1.5, ease_in_elastic_small),
                    Delay(1.)))
        elif self.text.done:
            self.stop()

    def setup(self):
        self.mouse.cursor = HIDDEN
        self.text.x = (self.width - self.text.width) / 2
        self.text.y = self.height

    def draw(self):
        self.clear()
        background(0.0)


canvas = MyCanvas()
width = min(1024, canvas.screen.width)
aspect = width / canvas.screen.height
canvas.size = (width, int(width * (1.0 / aspect)))
canvas.fullscreen = True
canvas.run()
