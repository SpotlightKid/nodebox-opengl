# Add the upper directory (where the nodebox module is) to the search path.
import os, sys; sys.path.insert(0, os.path.join("..", ".."))

import subprocess as sp

import pyglet

from nodebox.graphics import *
from nodebox.util.movie import *


def draw(canvas):
    canvas.clear()
    background(1)
    translate(250, 250)
    rotate(canvas.frame)
    rect(-100, -100, 200, 200)
    movie.record() # Capture each frame.


canvas.size = 500, 500
canvas.fps = 25
movie = Movie(canvas, "test.mp4")
canvas.run(draw)
movie.save()
