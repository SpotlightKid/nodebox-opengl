#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import division, print_function, unicode_literals

# Add the upper directory (where the nodebox module is) to the search path.
import os, sys; sys.path.insert(0, os.path.join("..", ".."))

from nodebox.graphics import *


class MyCanvas(Canvas):
    def __init__(self, *args, **kwargs):
        Canvas.__init__(self, *args, **kwargs)
        txt = Text("NodeBox for OpenGL",
                   font="Times New Roman",
                   fontsize=75,
                   fontweight=BOLD,
                   lineheight=1.2,
                   fill=color(0.2, 0.2, 255 / 128))

        def render_text():
            text(txt, 0, 30)

        img = render(render_text, textwidth(txt) + 20, 110)
        self.img = bloom(img, intensity=3.0)
        shadow = desaturate(img)
        self.shadow = blur(shadow, amount=3.0, kernel=5)
        self.speed = 1.5  # pixels/second
        self.pos = -self.img.height

    def on_key_press(self, keys):
        Canvas.on_key_press(self, keys)

        if keys.code == 'f11':
            self.fullscreen = not self.fullscreen

    def draw(self):
        x = (self.width - self.img.width) / 2
        y = self.pos

        self.clear()
        background(0.0)
        image(self.shadow, x=x + 5, y=y - 5, alpha=0.7)
        image(self.img, x, y)

        self.pos += self.speed
        if self.pos > self.height:
            self.pos = -self.img.height


canvas = MyCanvas(width=1024, height=600)
canvas.run()
