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
                   x=2, y=30,
                   font="Times New Roman",
                   fontsize=75,
                   fontweight=BOLD,
                   lineheight=1.2,
                   fill=color(0.))

        def render_text():
            text(txt)

        self.img = render(render_text, textwidth(txt) + 20, 110)
        self.shadow = dropshadow(self.img, amount=3.0)
        self.speed = 50  # pixels/second

    def on_resize(self):
        self.text_x = (self.width - self.img.width) / 2

    def setup(self):
        self.text_x = (self.width - self.img.width) / 2
        self.text_y = -self.img.height
        self.mouse.cursor = HIDDEN

    def update(self):
        self.text_y += self.speed * self.elapsed

        if self.text_y > self.height:
            self.text_y = -self.img.height

    def draw(self):
        self.clear()
        background(1.0)
        image(self.shadow, self.text_x + 4, self.text_y - 4)
        image(self.img, self.text_x, self.text_y)


canvas = MyCanvas()
aspect = canvas.screen.width / canvas.screen.height
canvas.size = (1024, int(1024 * (1.0 / aspect)))
canvas.run()
