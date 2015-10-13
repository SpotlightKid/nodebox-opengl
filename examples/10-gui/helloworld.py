#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import absolute_import, print_function, unicode_literals

from nodebox.graphics import Canvas
from nodebox.gui.controls import Button


def hello(control, *args, **kwargs):
    print("Action of control '%s' triggered." % control.id)
    print("Hello World!")

canvas = Canvas(name="Hello World", width=480, height=320)
button = Button("Push me!", id="hellobutton", action=hello)
canvas.append(button)
button.x = canvas.width / 2 - button.width / 2
button.y = canvas.height / 2 - button.height / 2

def draw(canvas):
    canvas.clear()

canvas.run(draw)
