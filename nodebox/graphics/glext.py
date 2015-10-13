# -*- coding: utf-8 -*-
"""OpenGL utility convenience functions."""

from pyglet.gl import *

# Stroke styles
STROKE_SOLID = "solid"
STROKE_DOTTED = "dotted"
STROKE_DASHED = "dashed"


def glLineDash(style):
    if style == STROKE_SOLID:
        glDisable(GL_LINE_STIPPLE)
    elif style == STROKE_DOTTED:
        glEnable(GL_LINE_STIPPLE)
        glLineStipple(0, 0x0101)
    elif style == STROKE_DASHED:
        glEnable(GL_LINE_STIPPLE)
        glLineStipple(1, 0x000F)
