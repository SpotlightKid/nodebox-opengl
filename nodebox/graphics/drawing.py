# -*- coding: utf-8 -*-
"""Global drawing state manipulation and transformation functions."""

from __future__ import absolute_import

from pyglet.gl import *

from .color import Color
from .geometry import AffineTransform as Transform
from .state import global_state as _g, state_mixin

__all__ = (
    'STROKE_SOLID',
    'STROKE_DASHED',
    'STROKE_DOTTED',
    'Transform',
    'background',
    'colormode',
    'fill',
    'glLineDash',
    'nofill',
    'nostroke',
    'outputmode',
    'pop',
    'push',
    'reset',
    'rotate',
    'scale',
    'skew',
    'stroke',
    'strokestyle',
    'strokewidth',
    'transform',
    'translate',
)

# Stroke styles
STROKE_SOLID = "solid"
STROKE_DOTTED = "dotted"
STROKE_DASHED = "dashed"


# -- Drawing state ------------------------------------------------------------

def background(*args, **kwargs):
    """Set the current background color."""
    if args:
        _g.background = Color(*args, **kwargs)
        xywh = (GLint * 4)()
        glGetIntegerv(GL_VIEWPORT, xywh)
        x, y, w, h = xywh
        rect(x, y, w, h, fill=_g.background, stroke=None)

    return _g.background


def fill(*args, **kwargs):
    """Set the current fill color for drawing primitives and paths."""
    if args:
        _g.fill = Color(*args, **kwargs)

    return _g.fill


def stroke(*args, **kwargs):
    """Set the current stroke color."""
    if args:
        _g.stroke = Color(*args, **kwargs)

    return _g.stroke


def nofill():
    """No current fill color."""
    _g.fill = None


def nostroke():
    """No current stroke color."""
    _g.stroke = None


def strokewidth(width=None):
    """Set the outline stroke width."""
    # Note: strokewidth is clamped to integers (e.g. 0.2 => 1),
    # but finer lines can be achieved visually with a transparent stroke.
    # Thicker strokewidth results in ugly (i.e. no) line caps.
    if width is not None:
        _g.strokewidth = width
        glLineWidth(width)

    return _g.strokewidth


def strokestyle(style=None):
    """Set the outline stroke style (SOLID / DOTTED / DASHED)."""
    if style is not None and style != _g.strokestyle:
        _g.strokestyle = style
        glLineDash(style)

    return _g.strokestyle


def outputmode(mode=None):
    raise NotImplementedError


def colormode(mode=None, range=1.0):
    raise NotImplementedError


def glLineDash(style):
    if style == STROKE_SOLID:
        glDisable(GL_LINE_STIPPLE)
    elif style == STROKE_DOTTED:
        glEnable(GL_LINE_STIPPLE)
        glLineStipple(0, 0x0101)
    elif style == STROKE_DASHED:
        glEnable(GL_LINE_STIPPLE)
        glLineStipple(1, 0x000F)


# -- Transformations ----------------------------------------------------------

# Unlike NodeBox, all transformations are CORNER-mode and originate from the
# bottom-left corner.

# Example: using Transform to get a transformed path:
#
#     t = Transform()
#     t.rotate(45)
#     p = BezierPath()
#     p.rect(10, 10, 100, 70)
#     p = t.transform_path(p)
#     p.contains(x, y) # check if the mouse is in the transformed shape.

def push():
    """Push the transformation state.

    Subsequent transformations (translate, rotate, scale) remain in effect
    until pop() is called.

    """
    glPushMatrix()


def pop():
    """Pop the transformation state.

    This reverts the transformation to before the last push().

    """
    glPopMatrix()


def translate(x, y, z=0):
    """Translate coordinate system origin.

    By default, the origin of the layer or canvas is at the bottom left.

    This origin point will be moved by (x,y) pixels.

    """
    glTranslatef(round(x), round(y), round(z))


def rotate(degrees, axis=(0, 0, 1)):
    """Rotate the transformation state.

    This has the effect that all subsequent drawing primitives are rotated.

    Rotations work incrementally: calling rotate(60) and rotate(30) sets the
    current rotation to 90.

    """
    glRotatef(degrees, *axis)


def scale(x, y=None, z=None):
    """Scale the transformation state."""
    if y is None:
        y = x
    if z is None:
        z = 1
    glScalef(x, y, z)


def reset():
    """Reset the transform state of the layer or canvas."""
    glLoadIdentity()


# XXX: WTF?
def transform(mode=None):
    if mode == "center":
        raise NotImplementedError("no center-mode transform")
    return "corner"


def skew(x, y):
    raise NotImplementedError
