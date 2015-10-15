# -*- coding: utf-8 -*-
"""Module to keep global drawing state."""

__all__ = ('State', 'global_state', 'state_mixin')


class State(object):
    def __init__(self):
        self.alpha = 1              # alpha transparency for drawing commands
        self.autoclosepath = True   # whether to auto-close bezier paths
        self.background = None      # background color for drawing commands
        self.fill = None            # fill color for drawing commands and text
        self.stroke = None          # stroke color for drawing commands
        self.strokewidth = 1        # stroke width for drawing commands
        self.strokestyle = "solid"  # stroke style for drawing commands
        self.path = None            # current bezier path


global_state = State()


# -- STATE MIXIN --------------------------------------------------------------
# Drawing commands like rect() have optional parameters fill and stroke to set
# the color directly.

def state_mixin(**kwargs):
    fill = kwargs.get("fill", global_state.fill)
    stroke = kwargs.get("stroke", global_state.stroke)
    strokewidth = kwargs.get("strokewidth", global_state.strokewidth)
    strokestyle = kwargs.get("strokestyle", global_state.strokestyle)
    return (fill, stroke, strokewidth, strokestyle)
