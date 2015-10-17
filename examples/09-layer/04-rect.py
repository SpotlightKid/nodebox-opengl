# Add the upper directory (where the nodebox module is) to the search path.
import os, sys; sys.path.insert(0, os.path.join("..",".."))

# Import the drawing commands from the NodeBox module.
from nodebox.graphics import *

# Draw layer content: a simple orange square
def draw(layer):
    fill(1.0, 0.7, 0.1)
    rect(x=100, y=10, width=300, height=300)

layer = Layer(0, 0, name='rect')
layer.set_method(draw, name="draw")
layer.opacity = 0.5  # layer is semi-transparent
canvas.append(layer)
canvas.size = 500, 500
canvas.run()
