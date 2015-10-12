# -*- coding: utf-8 -*-

# === CONTROLS ================================================================
# Native GUI controls.
# Authors: Tom De Smedt
# License: BSD (see LICENSE.txt for details).
# Copyright (c) 2008-2012 City In A Bottle (cityinabottle.org)
# http://cityinabottle.org/nodebox

from __future__ import absolute_import, print_function

from glob import glob
from time import time

from os.path import abspath, basename, dirname, join, splitext

from pyglet.text.layout import IncrementalTextLayout
from pyglet.text.caret import Caret

from nodebox.graphics.geometry import clamp, INFINITE
from nodebox.graphics import (
    Layer, Color, Image, image, crop,
    Text, NORMAL, BOLD, DEFAULT_FONT, install_font,
    translate, rotate, lighter,
    line, DASHED, DOTTED,
    DEFAULT, HAND, TEXT,
    LEFT, RIGHT, UP, DOWN, TAB, ENTER, BACKSPACE, DELETE, CTRL, SHIFT, ALT)

TOP, BOTTOM, CENTER = "top", "bottom", "center"


def _find(func, seq, default=None):
    """Return index of first item in sequence for which func(item) is True.

    If no item matches, return default (None) instead.

    """
    for i, item in enumerate(seq):
        if func(item):
            return i
    else:
        return default


# =============================================================================

# -- Theme --------------------------------------------------------------------

class Theme(dict):
    """Defines the source images for controls and font settings for labels.

    A theme is loaded from a given folder path (containing PNG images and TTF
    font files). The default theme is in nodebox/graphics/gui/theme/ Copy this
    folder and modify it to create a custom theme.

    """
    def __init__(self, path, **kwargs):
        """Initialize the from files in given directory.

        The directoy must contain all the necessary image and font files.
        See the default themes for the standard file names.

        """
        # Filename is assumed to be fontname.
        dict.__init__(self, ((basename(splitext(f)[0]), f)
                  for f in glob(join(path, "*.png"))))
        self["fonts"] = [basename(splitext(f)[0])
                         for f in glob(join(path, "*.ttf")) if install_font(f)]
        self["fontname"] = kwargs.get("fontname", self["fonts"][-1]
                                      if self["fonts"] else DEFAULT_FONT)
        self["fontsize"] = kwargs.get("fontsize", 10)
        self["fontweight"] = kwargs.get("fontweight", NORMAL)
        self["text"] = kwargs.get("text", Color(1.0))


theme = Theme(join(dirname(abspath(__file__)), "theme"))


# =============================================================================

# -- Control ------------------------------------------------------------------

class Control(Layer):
    """Base class for GUI controls.

    The Control class inherits from Layer so it must be appended to the
    canvas (or a container) to receive events and get drawn.

    An id can be given to uniquely identify the control. If the control is
    part of a Panel, it can be retrieved with Panel.control_id.

    """
    def __init__(self, x=0, y=0, id=None, color=(1, 1, 1, 1), **kwargs):
        Layer.__init__(self, x=x, y=y, **kwargs)
        self.id = id
        self.src = {}        # Collection of source images.
        self.color = color   # Color for source images.
        self.enabled = True  # Enable event listener.
        self.duration = 0    # Disable tweening.
        self._controls = {}  # Lazy index of (id, control) children, see nested().
        self._press = None

    # Control width and height can't be modified after creation.
    # Internally, use Layer._set_width() and Layer._set_height().
    @property
    def width(self):
        return self._get_width()

    @property
    def height(self):
        return self._get_height()

    def on_mouse_enter(self, mouse):
        mouse.cursor = HAND

    def on_mouse_leave(self, mouse):
        mouse.cursor = DEFAULT

    def on_mouse_press(self, mouse):
        # Fire Control.on_mouse_doubleclick() when mouse is pressed twice
        # in same location.
        # Subclasses need to call this method in their overridden
        # on_mouse_press().
        if (self._press and
                abs(self._press[0] - mouse.x) < 2 and
                abs(self._press[1] - mouse.y) < 2 and
                self._press[2] == mouse.button and
                self._press[3] == mouse.modifiers and
                self._press[4] - time() > -0.4):
            self._press = None
            self.on_mouse_doubleclick(mouse)
        self._press = (mouse.x, mouse.y, mouse.button, mouse.modifiers, time())

    def on_mouse_doubleclick(self, mouse):
        pass

    def on_key_press(self, keys):
        for control in self:
            control.on_key_press(keys)

    def on_key_release(self, keys):
        for control in self:
            control.on_key_release(keys)

    def on_action(self):
        """Override this method with a custom action."""
        pass

    def reset(self):
        pass

    def _draw(self):
        Layer._draw(self)

    # Control._pack() is called internally to layout child controls.
    # This should not happen in Control.update(), which is called every frame.
    def _pack(self):
        pass

    # With transformed=True, expensive matrix transformations are done.
    # Turn off, controls are not meant to be rotated or scaled.
    def layer_at(self, x, y, clipped=False, enabled=False, transformed=True,
                 _covered=False):
        return Layer.layer_at(self, x, y, clipped, enabled, False, _covered)

    def origin(self, x=None, y=None, relative=False):
        return Layer.origin(self, x, y, relative)

    def rotate(self, angle):
        pass

    def scale(self, f):
        pass

    def __getattr__(self, k):
        # Yields the property with the given name, or
        # yields the child control with the given id.
        if k in self.__dict__:
            return self.__dict__[k]
        ctrl = nested(self, k)
        if ctrl is not None:
            return ctrl
        raise AttributeError("'%s' object has no attribute '%s'" %
                             (self.__class__.__name__, k))

    def __repr__(self):
        return "%s(id=%s%s)" % (
            self.__class__.__name__,
            repr(self.id),
            hasattr(self, "value") and ", value="+repr(self.value) or ""
        )

def nested(control, id):
    """Return the child Control with the given id, or None.

    Also searches all child Layout containers.

    """
    # First check the Control._controls cache (=> 10x faster).
    # Also check if the control's id changed after it was cached (however unlikely).
    # If so, the cached entry is no longer valid.
    if id in control._controls:
        ctrl = control._controls[id]
        if ctrl.id == id:
            return ctrl
        del control._controls[id]
    # Nothing in the cache.
    # Traverse all child Control and Layout objects.
    m = None
    for ctrl in control:
        if ctrl.__dict__.get("id") == id:
            m = ctrl; break
        if isinstance(ctrl, Layout):
            m = nested(ctrl, id)
            if m is not None:
                break
    # If a control was found, cache it.
    if m is not None:
        control._controls[id] = m
    return m

# =============================================================================

# -- Label --------------------------------------------------------------------

class Label(Control):
    """A label displays a given caption, centered in the label's box.

    The label does not receive any events.

    """
    def __init__(self, caption, x=0, y=0, width=None, height=None, id=None,
                 **kwargs):
        """Create a label with the given caption.

        Accepts the same keyword arguments as Control, i.e. x, y, and id.
        The dimension can be given with width, height.

        Additional, optional keyword parameters are align, fill, font,
        fontsize, fontweight and lineheight.

        """
        txt = Text(caption, **{
            "fill": kwargs.pop("fill", theme["text"]),
            "font": kwargs.pop("font", theme["fontname"]),
            "fontsize": kwargs.pop("fontsize", theme["fontsize"]),
            "fontweight": kwargs.pop("fontweight", theme["fontweight"]),
            "lineheight": 1,
            "align": CENTER
        })
        kwargs.setdefault("width", txt.metrics[0])
        kwargs.setdefault("height", txt.metrics[1])
        Control.__init__(self, x=x, y=y, id=id, **kwargs)
        self.enabled = False # Pass on events to the layers underneath.
        self._text = txt
        self._pack()

    @property
    def caption(self):
        return self._text.text

    @caption.setter
    def caption(self, string):
        self._text.text = string
        self._pack()

    @property
    def font(self):
        return self._text.font

    @property
    def fontsize(self):
        return self._text.fontsize

    @property
    def fontweight(self):
        return self._text.fontweight

    def _pack(self):
        # Center the text inside the label.
        self._text.x = 0.5 * (self.width - self._text.metrics[0])
        self._text.y = 0.5 * (self.height - self._text.metrics[1])

    def draw(self):
        self._text.draw()

# =============================================================================

# -- BUTTON -------------------------------------------------------------------

class Button(Control):
    """A clickable button that will fire Button.on_action() when clicked.

    The action handler can be defined in a subclass, or given as a function.

    """
    def __init__(self, caption="", action=None, x=0, y=0, width=125, id=None,
                 **kwargs):
        Control.__init__(self, x=x, y=y, width=width, id=id, **kwargs)
        img = Image(theme["button"])
        w = 20
        self.src = {
            "face": crop(img, w, 0, 1, img.height),
            "cap1": crop(img, 0, 0, w, img.height),
            "cap2": crop(img, img.width - w, 0, w, img.height),
        }

        if action:
            # Override the Button.on_action() method from the given function.
            self.set_method(action, name="on_action")

        kwargs.pop("width", None)
        kwargs.pop("height", None)
        self.offset = 2
        self.append(Label(caption, **kwargs))
        self._pack()

    @property
    def caption(self):
        return self[0].caption

    @caption.setter
    def caption(self, text):
        self[0].caption = text
        self._pack()

    def _pack(self):
        # Button size can not be smaller than its caption.
        w = max(self.width, self[0].width + self[0].fontsize * 2)
        self._set_width(w)
        self._set_height(self.src["face"].height)

    def update(self):
        # Center the text inside the button.
        # This happens each frame because the position changes when the button
        # is pressed.
        self[0].x = 0.5 * (self.width - self[0].width)
        self[0].y = 0.5 * (self.height - self[0].height) - (
                    self.offset if self.pressed else 0)

    def draw(self):
        #clr = [v * 0.75 for v in self.color] if self.pressed else self.color
        clr = lighter(self.color) if self.pressed else self.color
        im1, im2, im3 = self.src["cap1"], self.src["cap2"], self.src["face"]
        image(im1, 0, 0, height=self.height, color=clr)
        image(im2, x=self.width - im2.width, height=self.height, color=clr)
        image(im3, x=im1.width, width=self.width-im1.width-im2.width,
              height=self.height, color=clr)

    def on_mouse_release(self, mouse):
        Control.on_mouse_release(self, mouse)
        if self.contains(mouse.x, mouse.y, transformed=False):
            # Only fire event if mouse is actually released on the button.
            self.on_action()

# -- ACTION -------------------------------------------------------------------

class Action(Control):

    def __init__(self, action=None, x=0, y=0, id=None, **kwargs):
        """A clickable button that will fire Action.on_action() when clicked.

        Actions display an icon instead of a text caption.

        Actions are meant to be used for interface management: e.g. closing or
        minimizing a panel, navigating to the next page, ...

        """
        Control.__init__(self, x=x, y=y, id=id, **kwargs)
        self.src = {"face": Image(theme["action"])}
        self._pack()
        if action:
            # Override the Button.on_action() method from the given function.
            self.set_method(action, name="on_action")

    def _pack(self):
        self._set_width(self.src["face"].width)
        self._set_height(self.src["face"].height)

    def draw(self):
        clr = [v * 0.75 for v in self.color] if self.pressed else self.color
        image(self.src["face"], 0, 0, color=clr)

    def on_mouse_release(self, mouse):
        Control.on_mouse_release(self, mouse)
        if self.contains(mouse.x, mouse.y, transformed=False):
            # Only fire event if mouse is actually released on the button.
            self.on_action()


class Close(Action):

    def __init__(self, action=None, x=0, y=0, id=None, **kwargs):
        """An action that hides the parent control (e.g. a Panel) when pressed.
        """
        Action.__init__(self, action, x=x, y=y, id=id, **kwargs)
        self.src["face"] = Image(theme["action-close"])

    def on_action(self):
        self.parent.hidden = True


# =============================================================================

# -- SLIDER -------------------------------------------------------------------

class Handle(Control):

    def __init__(self, parent):
        # The slider handle can protrude from the slider bar,
        # so it is a separate layer that fires its own events.
        Control.__init__(self, width=parent.src["handle"].width,
                         height=parent.src["handle"].height)
        self.parent = parent

    def on_mouse_press(self, mouse):
        self.parent.on_mouse_press(mouse)

    def on_mouse_drag(self, mouse):
        self.parent.on_mouse_drag(mouse)

    def on_mouse_release(self, mouse):
        self.parent.on_mouse_release(mouse)

    def draw(self):
        clr = ([v * 0.75 for v in self.color]
               if self.parent.pressed or self.pressed else self.color)
        image(self.parent.src["handle"], 0, 0, color=clr)


class Slider(Control):

    def __init__(self, default=0.5, min=0.0, max=1.0, steps=100, x=0, y=0,
                 width=125, id=None, **kwargs):
        """A draggable slider that will fire Slider.on_action() when dragged.

        The slider's value can be retrieved with Slider.value.

        """
        Control.__init__(self, x=x, y=y, width=width, id=id, **kwargs)
        self.min = min     # Slider minimum value.
        self.max = max     # Slider maximum value.
        self.default = default # Slider default value.
        self.value = default # Slider current value.
        self.steps = steps   # Number of steps from min to max.
        img, w = Image(theme["slider"]), 5
        self.src = {
            "face1" : crop(img, w, 0, 1, img.height),
            "face2" : crop(img, img.width-w, 0, 1, img.height),
             "cap1" : crop(img, 0, 0, w, img.height),
             "cap2" : crop(img, img.width-w, 0, w, img.height),
           "handle" : Image(theme["slider-handle"])
        }
        # The handle is a separate layer.
        self.append(Handle(self))
        self._pack()

    @property
    def value(self):
        return self.min + self._t * (self.max - self.min)

    @value.setter
    def value(self, value):
        self._t = clamp(float(value - self.min) / (self.max - self.min or -1),
                        0.0, 1.0)

    @property
    def relative(self):
        """Yield the slider position as a relative number (0.0-1.0)."""
        return self._t

    def _pack(self):
        w = max(self.width, self.src["cap1"].width + self.src["cap2"].width)
        self._set_width(w)
        self._set_height(self.src["face1"].height)

    def reset(self):
        Control.reset(self)
        self.value = self.default

    def update(self):
        # Update the handle's position, before Slider.draw() occurs (=smoother)
        self[0].x = self._t * self.width - 0.5 * self[0].width
        self[0].y = 0.5 * (self.height - self[0].height)

    def draw(self):
        t = self._t * self.width
        clr = self.color
        im1, im2, im3, im4 = (self.src["cap1"], self.src["cap2"],
                              self.src["face1"], self.src["face2"])
        image(im1, x=0, y=0, color=clr)
        image(im2, x=self.width-im2.width, y=0, color=clr)
        image(im3, x=im1.width, y=0, width=t-im1.width, color=clr)
        image(im4, x=t, y=0, width=self.width-t-im2.width+1, color=clr)

    def on_mouse_press(self, mouse):
        x0, y0 = self.absolute_position() # Can be nested in other layers.
        step = 1.0 / max(self.steps, 1)
        # Calculate relative value from the slider handle position.
        # The inner width is a bit smaller to accomodate for the slider handle.
        # Clamp the relative value to the nearest step.
        self._t = ((mouse.x - x0 - self.height * 0.5) /
                   float(self.width - self.height))
        self._t = self._t - self._t % step + step
        self._t = clamp(self._t, 0.0, 1.0)
        self.on_action()

    def on_mouse_drag(self, mouse):
        self.on_mouse_press(mouse)


# =============================================================================

# -- KNOB ---------------------------------------------------------------------

class Knob(Control):

    def __init__(self, default=0, limit=True, x=0, y=0, id=None, **kwargs):
        """A twistable knob that will fire Knob.on_action() when dragged.

        The knob's angle can be retrieved with Knob.value (in degrees, 0-360).
        With CTRL pressed, twists by a very small amount.

        """
        Control.__init__(self, x=x, y=y, id=id, **kwargs)
        self.default = default # Knob default angle.
        self.value = default # Knob current angle.
        self._limit = limit   # Constrain between 0-360 or scroll endlessly?
        self.src = {
            "face" : Image(theme["knob"]),
          "socket" : Image(theme["knob-socket"]),
        }
        self._pack()

    @property
    def relative(self):
        """ Yields the knob's angle as a relative number (0.0-1.0).
        """
        return self.value % 360 / 360.0

    def _pack(self):
        self._set_width(self.src["socket"].width)
        self._set_height(self.src["socket"].height)

    def reset(self):
        Control.reset(self)
        self.value = self.default

    def draw(self):
        clr1 = self.color
        clr2 = [v * 0.85 for v in self.color] if self.pressed else self.color
        translate(self.width/2, self.height/2)
        image(self.src["socket"], -self.width/2, -self.height/2, color=clr1)
        rotate(360-self.value)
        image(self.src["face"], -self.width/2, -self.height/2, color=clr2)

    def on_mouse_press(self, mouse):
        self.value += mouse.dy * (CTRL in mouse.modifiers and 1 or 5)
        if self._limit:
            self.value %= 360
        self.on_action()

    def on_mouse_drag(self, mouse):
        self.on_mouse_press(mouse)

# =============================================================================

# -- FLAG ---------------------------------------------------------------------

class Flag(Control):

    def __init__(self, default=False, x=0, y=0, id=None, **kwargs):
        """ A checkbox control that fires Flag.on_action() when checked.
            The checkbox value can be retrieved with Flag.value.
        """
        Control.__init__(self, x=x, y=y, id=id, **kwargs)
        self.default = bool(default) # Flag default value.
        self.value = bool(default) # Flag current value.
        self.src = {
            "face" : Image(theme["flag"]),
         "checked" : Image(theme["flag-checked"]),
        }
        self._pack()

    def _pack(self):
        self._set_width(self.src["face"].width)
        self._set_height(self.src["face"].height)

    def reset(self):
        self.value = self.default

    def draw(self):
        clr = self.color
        image(self.value and self.src["checked"] or self.src["face"], color=clr)

    def on_mouse_release(self, mouse):
        Control.on_mouse_release(self, mouse)
        if self.contains(mouse.x, mouse.y, transformed=False):
            # Only change status if mouse is actually released on the button.
            self.value = not self.value
            self.on_action()

Checkbox = CheckBox = Flag

# =============================================================================

# -- Editable -----------------------------------------------------------------

EDITING = None
editing = lambda: EDITING

class Editable(Control):
    """An editable text box.

    When clicked, it has the focus and can receive keyboard events.

    """
    def __init__(self, value="", x=0, y=0, width=125, height=20, padding=(0,0),
                 wrap=False, id=None, **kwargs):
        """Create an editable box.

        value is the initial text.

        With wrap=True, several lines of text will wrap around the width.

        Optional parameters can include fill, font, fontsize, fontweight.

        """
        txt = Text(value or " ", **{
               "fill" : kwargs.pop("fill", Color(0,0.9)),
               "font" : kwargs.pop("font", theme["fontname"]),
           "fontsize" : kwargs.pop("fontsize", theme["fontsize"]),
         "fontweight" : kwargs.pop("fontweight", theme["fontweight"]),
         "lineheight" : kwargs.pop("lineheight", wrap and 1.25 or 1.0),
              "align" : LEFT
        })
        kwargs["width"] = width
        kwargs["height"] = height
        Control.__init__(self, x=x, y=y, id=id, **kwargs)
        self.reserved = kwargs.get("reserved", [ENTER, TAB])
        self._padding = padding
        self._i = 0  # Index of character on which the mouse is pressed.
        self._empty = value == ""
        self._editor = IncrementalTextLayout(txt._label.document, width,
                                             height, multiline=wrap)
        self._editor.content_valign = "top" if wrap else "center"
        self._editor.selection_background_color = (170, 200, 230, 255)
        self._editor.selection_color = txt._label.color
        self._editor.caret = Caret(self._editor)
        self._editor.caret.visible = False
        self._editing = False # When True, cursor is blinking and text can be edited.
        Editable._pack(self)  # On init, call Editable._pack(), not the derived Field._pack().

    def _pack(self):
        self._editor.x = self._padding[0]
        self._editor.y = self._padding[1]
        self._editor.width = max(0, self.width  - self._padding[0] * 2)
        self._editor.height = max(0, self.height - self._padding[1] * 2)

    @property
    def value(self):
        # IncrementalTextLayout in Pyglet 1.1.4 has a bug with empty strings.
        # We keep track of empty strings with Editable._empty to avoid this.
        return u"" if self.empty else self._editor.document.text

    @value.setter
    def value(self, string):
        self._editor.begin_update()
        self._editor.document.text = string or " "
        self._editor.end_update()
        self._empty = string == "" and True or False

    @property
    def editing(self):
        return self._editing

    @editing.setter
    def editing(self, b):
        global EDITING

        self._editing = b
        self._editor.caret.visible = b

        if b is False and EDITING == self:
            EDITING = None
        if b is True:
            EDITING = self
            # Cursor is blinking and text can be edited.
            # Visit all layers on the canvas.
            # Remove the caret from all other Editable controls.
            for layer in (self.root.canvas and self.root.canvas.layers or []):
                layer.traverse(visit=lambda layer: \
                    isinstance(layer, Editable) and layer != self and \
                        setattr(layer, "editing", False))

    @property
    def selection(self):
        # Yields a (start, stop)-tuple with the indices of the current selected text.
        return (self._editor.selection_start, self._editor.selection_end)

    @property
    def selected(self):
        # Yields True when text is currently selected.
        return self.selection[0] != self.selection[1]

    @property
    def cursor(self):
        # Yields the index at the text cursor (caret).
        return self._editor.caret.position

    def index(self, x, y):
        """Return the index of the character in the text at position x, y."""
        x0, y0 = self.absolute_position()
        i = self._editor.get_position_from_point(x-x0, y-y0)
        if self._editor.get_point_from_position(0)[0] > x-x0: # Pyglet bug?
            i = 0
        if self._empty:
            i = 0
        return i

    def on_mouse_enter(self, mouse):
        mouse.cursor = TEXT

    def on_mouse_press(self, mouse):
        i = self._i = self.index(mouse.x, mouse.y)
        self._editor.set_selection(0, 0)
        self.editing = True
        self._editor.caret.position = i
        Control.on_mouse_press(self, mouse)

    def on_mouse_release(self, mouse):
        if self._editor.selection_end:
            self._editor.caret.position = self._editor.selection_end
            self._editor.caret.visible = True
        elif not self.dragged:
            self._editor.caret.position = self.index(mouse.x, mouse.y)
        Control.on_mouse_release(self, mouse)

    def on_mouse_drag(self, mouse):
        i = self.index(mouse.x, mouse.y)
        self._editor.selection_start = max(min(self._i, i), 0)
        self._editor.selection_end = min(max(self._i, i), len(self.value))
        self._editor.caret.visible = False
        Control.on_mouse_drag(self, mouse)

    def on_mouse_doubleclick(self, mouse):
        # Select the word at the mouse position.
        # Words are delimited by non-alphanumeric characters.
        i = self.index(mouse.x, mouse.y)
        delimiter = lambda ch: not (ch.isalpha() or ch.isdigit())

        if i < len(self.value) and delimiter(self.value[i]):
            self._editor.set_selection(i, i+1)

        if i == len(self.value) and self.value and delimiter(self.value[i-1]):
            self._editor.set_selection(i-1, i)

        a = _find(delimiter, reversed(self.value[:i]), 0)
        b = _find(delimiter, self.value[i:], len(self.value))
        self._editor.set_selection(a, b)

    def on_key_press(self, keys):
        if self._editing:
            self._editor.caret.visible = True
            i = self._editor.caret.position

            if keys.code == LEFT:
                # The left arrow moves the text cursor to the left.
                self._editor.caret.position = max(i-1, 0)
            elif keys.code == RIGHT:
                # The right arrow moves the text cursor to the right.
                self._editor.caret.position = min(i+1, len(self.value))
            elif keys.code in (UP, DOWN):
                # The up arrows moves the text cursor to the previous line.
                # The down arrows moves the text cursor to the next line.
                y = keys.code == UP and -1 or +1
                n = self._editor.get_line_count()
                i = self._editor.get_position_on_line(
                    min(max(self._editor.get_line_from_position(i)+y, 0), n-1),
                            self._editor.get_point_from_position(i)[0])
                self._editor.caret.position = i
            elif keys.code == TAB and TAB in self.reserved:
                # The tab key navigates away from the control.
                self._editor.caret.position = 0
                self.editing = False
            elif keys.code == ENTER and ENTER in self.reserved:
                # The enter key executes on_action() and navigates away from the control.
                self._editor.caret.position = 0
                self.editing = False
                self.on_action()
            elif keys.code in (BACKSPACE, DELETE) and self.selected:
                # The backspace key removes the current text selection.
                self.value = self.value[:self.selection[0]] + self.value[self.selection[1]:]
                self._editor.caret.position = max(self.selection[0], 0)
            elif keys.code == BACKSPACE and i > 0:
                # The backspace key removes the character at the text cursor.
                self.value = self.value[:i-1] + self.value[i:]
                self._editor.caret.position = max(i-1, 0)
            elif keys.code == DELETE and i < len(self.value):
                # The delete key removes the character to the right of text cursor.
                self.value = self.value[:i] + self.value[i+1:]
            elif keys.char:
                if self.selected:
                    # Typing replaces any text currently selected.
                    self.value = self.value[:self.selection[0]] + self.value[self.selection[1]:]
                    self._editor.caret.position = i = max(self.selection[0], 0)
                ch = keys.char
                ch = ch.replace("\r", "\n\r")
                self.value = self.value[:i] + ch + self.value[i:]
                self._editor.caret.position = min(i+1, len(self.value))

            self._editor.set_selection(0, 0)

    def draw(self):
        self._editor.draw()


# --- Field -------------------------------------------------------------------

class Field(Editable):
    """A single-line text input field.

    The string value can be retrieved with Field.value.

    """
    def __init__(self, value="", hint="", action=None, x=0, y=0, width=125,
                 padding=5, id=None, **kwargs):
        Editable.__init__(self, value, x=x, y=y, width=width,
                          padding=[padding]*2, id=id, **kwargs)
        img = Image(theme["field"])
        w = 10
        self.src = {
            "cap1": crop(img, 0, img.height - w, w, w),
            "cap2": crop(img, img.width - w, img.height - w, w, w),
            "cap3": crop(img, 0, 0, w, w),
            "cap4": crop(img, img.width - w, 0, w, w),
            "top": crop(img, w + 1, img.height - w, 1, w),
            "bottom": crop(img, w + 1, 0, 1, w),
            "left": crop(img, 0, w + 1, w, 1),
            "right": crop(img, img.width - w, w + 1, w, 1),
            "face": crop(img, w + 1, w + 1, 1, 1)
        }

        if action:
            # Override the Button.on_action() method from the given function.
            self.set_method(action, name="on_action")

        self.default = value
        self.append(Label(hint, fill=Color(0, 0.4)))
        self._pack()

    @property
    def hint(self):
        return self[0].caption

    @hint.setter
    def hint(self, text):
        self[0].caption = text

    def reset(self):
        self.value = self.default

    def _pack(self):
        Editable._pack(self)
        w = max(self.width, self.src["cap1"].width + self.src["cap2"].width)
        h = max(self.height, self.src["cap1"].width + self.src["cap3"].width)
        h = max(h, int(self._editor.document.get_style("line_spacing") * 1.5 +
                self._padding[1] * 2))
        self._set_width(w)
        self._set_height(h)
        # Position the hint text (if no other text is in the field).
        # The hint will not span multiple line if it is wider than the field
        # (it was designed to be a short word or phrase).
        self[0].x = self._padding[0]
        self[0].y = (self.height - self._padding[1] - self[0]._text.metrics[1]
                     * 1.25)
        self[0]._pack()

    def on_action(self):
        pass

    def update(self):
        self[0].hidden = self.editing or self.value != ""

    def draw(self):
        im1, im2, im3 = self.src["cap1"], self.src["cap2"], self.src["top"]
        im4, im5, im6 = self.src["cap3"], self.src["cap4"], self.src["bottom"]
        im7, im8, im9 = self.src["left"], self.src["right"], self.src["face"]
        clr = self.color
        image(im1, 0, self.height - im1.height, color=clr)
        image(im2, self.width - im2.width, self.height - im2.height, color=clr)
        image(im3, im1.width, self.height - im3.height,
              width=self.width - im1.width - im2.width, color=clr)
        image(im4, 0, 0, color=clr)
        image(im5, self.width - im5.width, 0, color=clr)
        image(im6, im4.width, 0, width=self.width - im4.width - im5.width,
              color=clr)
        image(im7, 0, im4.height, height=self.height - im1.height - im4.height,
              color=clr)
        image(im8, self.width - im8.width, im4.height,
              height=self.height - im2.height - im5.height, color=clr)
        image(im9, im4.width, im6.height,
              width=self.width - im7.width - im8.width,
              height=self.height - im3.height - im6.height, color=clr)
        Editable.draw(self)


# =============================================================================

# -- Rulers -------------------------------------------------------------------

class Rulers(Control):
    """A horizontal and vertical ruler displaying the width/height of the
    parent at intervals.

    A measurement line is drawn at each step(e.g. at 10 20 30...).

    A label with the value is drawn at each interval
    (e.g. 50 | | | | 100 | | | | 150).

    """
    def __init__(self, step=10, interval=5, crosshair=False,
                 color=(0, 0, 0, 1)):
        Control.__init__(self, x=0, y=0)
        self.enabled = False
        self.step = step
        self.interval = interval
        self.crosshair = crosshair
        self.color = color
        self._dirty = False
        self._markers = {}
        self._pack()

    @property
    def step(self):
        return self._step

    @step.setter
    def step(self, v):
        self._step = round(v)
        self._dirty = True

    @property
    def interval(self):
        return self._interval

    @interval.setter
    def interval(self, v):
        self._interval = round(v)
        self._dirty = True

    def _pack(self):
        # Cache Text objects for the measurement markers.
        # This happens whenever the canvas resizes, or the step or interval
        # changes. This will raise an error if the parent's width or height is
        # None (infinite).
        p = self.parent or self.canvas

        if (p and (self._dirty or self.width != p.width or
                self.height != p.height)):
            self._dirty = False
            self._set_width(p.width)
            self._set_height(p.height)

            for i in range(int(round(max(self.width, self.height) / self._step))):
                if i % self._interval == 0:
                    self._markers.setdefault(i * self._step,
                        Text(str(int(round(i * self._step))),
                             fontname=theme["fontname"],
                             fontsize=theme["fontsize"] * 0.6,
                             fill=self.color))

    def update(self):
        self._pack()

    def draw(self):
        length = 5

        # Draw the horizontal ruler.
        for i in range(1, int(round(self.height / self._step))):
            v, mark = i * self._step, i % self.interval == 0
            line(0, v, mark and length * 3 or length, v, stroke=self.color,
                 strokewidth=0.5)

            if mark:
                self._markers[v].draw(length * 3 - self._markers[v].metrics[0],
                                      v + 2)

        # Draw the vertical ruler.
        for i in range(1, int(round(self.width / self._step))):
            v, mark = i * self._step, i % self.interval == 0
            line(v, 0, v, mark and length * 3 or length, stroke=self.color,
                 strokewidth=0.5)

            if mark:
                self._markers[v].draw(v + 2,
                                      length * 3 - self._markers[v].fontsize)

        # Draw the crosshair.
        if self.crosshair:
            line(0, self.canvas.mouse.y, self.width, self.canvas.mouse.y,
                 stroke=self.color, strokewidth=0.5, strokestyle=DOTTED)
            line(self.canvas.mouse.x, 0, self.canvas.mouse.x, self.height,
                 stroke=self.color, strokewidth=0.5, strokestyle=DOTTED)


# =============================================================================

# -- PANEL --------------------------------------------------------------------

class Panel(Control):

    def __init__(self, caption="", fixed=False, modal=True, x=0, y=0,
                 width=175, height=250, **kwargs):
        """A panel containing other controls that can optonally be dragged.

        Set Panel.fixed = True (defaults to False) to allow a panel to be
        dragged.

        Controls or (Layout groups) can be added with Panel.append().

        """
        Control.__init__(self, x=x, y=y, width=max(width, 60),
                         height=max(height, 60), **kwargs)
        img, w = Image(theme["panel"]), 30
        self.src = {
            "cap1": crop(img, 0, img.height - w, w, w),
            "cap2": crop(img, img.width - w, img.height - w, w, w),
            "cap3": crop(img, 0, 0, w, w),
            "cap4": crop(img, img.width - w, 0, w, w),
            "top": crop(img, w + 1, img.height - w, 1, w),
            "bottom": crop(img, w + 1, 0, 1, w),
            "left": crop(img, 0, w + 1, w, 1),
            "right": crop(img, img.width - w, w + 1, w, 1),
            "face": crop(img, w + 1, w + 1, 1, 1)
        }
        self.append(Label(caption))
        self.append(Close())
        #self.extend(kwargs.pop("controls", []), **kwargs)
        self.fixed = fixed  # Draggable?
        self.modal = modal  # Closeable?
        self._pack()

    @property
    def caption(self):
        return self._caption.text

    @caption.setter
    def caption(self, text):
        self._caption.text = text
        self._pack()

    @property
    def controls(self):
        # self[0] is the Label,
        # self[1] is the Close action.
        return iter(self[2:])

    def insert(self, i, control):
        """ Inserts the control, or inserts all controls in the given Layout.
        """
        if isinstance(control, Layout):
            # If the control is actually a Layout (e.g. ordered group of
            # controls), apply it.
            control.apply()
        Layer.insert(self, i, control)

    def append(self, control):
        self.insert(len(self), control)

    def extend(self, controls):
        for control in controls:
            self.append(control)

    def _pack(self):
        # Center the caption in the label's header.
        # Position the close button in the top right corner.
        self[0].x = 0.5 * (self.width - self[0].width)
        self[0].y = (self.height - self.src["top"].height + 0.5 *
                     (self.src["top"].height - self[0].height))
        self[1].x = self.width - self[1].width - 4
        self[1].y = self.height - self[1].height - 2

    def pack(self, padding=20):
        """Resize the panel to the most compact size.

        Based on the position and size of the controls in the panel.

        """
        def _visit(control):
            if control not in (self, self[0], self[1]):
                self._b = (self._b.union(control.bounds)
                           if self._b else control.bounds)

        self._b = None
        self.traverse(_visit)

        for control in self.controls:
            control.x += padding + self.x - self._b.x
            control.y += padding + self.y - self._b.y

        self._set_width(padding + self._b.width + padding)
        self._set_height(padding + self._b.height + padding +
                         self.src["top"].height)
        self._pack()

    def update(self):
        self[1].hidden = self.modal
        self[1].color = self.color

    def draw(self):
        im1, im2, im3 = self.src["cap1"], self.src["cap2"], self.src["top"]
        im4, im5, im6 = self.src["cap3"], self.src["cap4"], self.src["bottom"]
        im7, im8, im9 = self.src["left"], self.src["right"], self.src["face"]
        clr = self.color
        image(im1, 0, self.height - im1.height, color=clr)
        image(im2, self.width - im2.width, self.height - im2.height, color=clr)
        image(im3, im1.width, self.height - im3.height, color=clr,
              width=self.width - im1.width - im2.width)
        image(im4, 0, 0, color=clr)
        image(im5, self.width - im5.width, 0, color=clr)
        image(im6, im4.width, 0, width=self.width - im4.width - im5.width,
              color=clr)
        image(im7, 0, im4.height, height=self.height - im1.height - im4.height,
              color=clr)
        image(im8, self.width - im8.width, im4.height, color=clr,
              height=self.height - im2.height - im5.height)
        image(im9, im4.width, im6.height, color=clr,
              width=self.width - im7.width - im8.width,
              height=self.height - im3.height - im6.height)

    def on_mouse_enter(self, mouse):
        mouse.cursor = DEFAULT

    def on_mouse_press(self, mouse):
        self._dragged = (not self.fixed and mouse.y > self.y + self.height -
                         self.src["top"].height)

    def on_mouse_drag(self, mouse):
        if self._dragged and not self.fixed:
            self.x += mouse.dx
            self.y += mouse.dy
        self.dragged = self._dragged

    def open(self):
        self.hidden = False

    def close(self):
        self.hidden = True


class Dock(Panel):
    """Panel attached to the edge of the canvas, extending the full height."""

    def __init__(self, caption="", anchor=LEFT, fixed=True, modal=True,
                 **kwargs):
        """Create a dock panel.

        To set the edge of the canvas, to which the dock is attached, pass LEFT
        or RIGHT with the anchor arg (defaullt LEFT).

        With fixed=False, it can be snapped from the edge and dragged as a
        normal panel.

        """
        kwargs.setdefault("x", anchor == RIGHT and INFINITE or 0)
        kwargs.setdefault("y", 0)
        Panel.__init__(self, caption=caption, fixed=fixed, modal=modal,
                       **kwargs)
        self.anchor = anchor
        self.snap = 1

    def update(self):
        Panel.update(self)

        if self.canvas is not None:
            if self.anchor == LEFT and self.x < self.snap:
                if self.dragged and self.x == 0:
                    # Stop drag once snapped to the edge.
                    self._dragged = False

                self.x = 0
                self.y = self.canvas.height - self.height

            if (self.anchor == RIGHT
                    and self.x > self.canvas.width - self.width - self.snap):
                if self.dragged and self.x == self.canvas.width - self.width:
                    self._dragged = False

                self.x = self.canvas.width - self.width
                self.y = self.canvas.height - self.height

    def draw(self):
        im1, im2 = self.src["top"], self.src["face"]
        if (self.canvas is not None and
                (self.anchor == LEFT and self.x == 0) or
                (self.anchor == RIGHT and
                self.x == self.canvas.width - self.width)):
            clr = self.color
            image(im1, 0, self.height - im1.height, width=self.width,
                  color=clr)
            image(im2, 0, -self.canvas.height + self.height, width=self.width,
                  height=self.canvas.height - im1.height, color=clr)
        else:
            Panel.draw(self)


# =============================================================================

# --- Layout ------------------------------------------------------------------

class Layout(Layer):
    """A group of controls with a specific layout.

    Controls can be added with Layout.append(). The layout will be applied when
    Layout.apply() is called. This happens automatically if a layout is
    appended to a Panel.

    """
    SPACING = 10  # Spacing between controls in a Layout.

    def __init__(self, controls=[], x=0, y=0, **kwargs):
        kwargs["width"] = 0
        kwargs["height"] = 0
        Layer.__init__(self, x=x, y=y, **kwargs)
        # Lazy cache of (id, control)-children, see nested().
        self._controls = {}
        self.spacing = kwargs.get("spacing", Layout.SPACING)
        self.extend(controls)

    def insert(self, i, control):
        """Insert the control, or inserts all controls in the given Layout."""
        if isinstance(control, Layout):
            # If the control is actually a Layout (e.g. ordered group of
            # controls), apply it.
            control.apply()
        Layer.insert(self, i, control)

    def append(self, control):
        self.insert(len(self), control)

    def extend(self, controls):
        for control in controls:
            self.append(control)

    def on_key_press(self, keys):
        for control in self:
            control.on_key_press(keys)

    def on_key_release(self, keys):
        for control in self:
            control.on_key_release(keys)

    def __getattr__(self, k):
        # Yields the property with the given name, or
        # yields the child control with the given id.
        if k in self.__dict__:
            return self.__dict__[k]
        ctrl = nested(self, k)
        if ctrl is not None:
            return ctrl
        raise AttributeError("'%s' object has no attribute '%s'" %
                             (self.__class__.__name__, k))

    def apply(self):
        """Adjust the position and size of the controls to match the layout."""
        self.width = max(control.width for control in self)
        self.height = max(control.height for control in self)

    def __repr__(self):
        return "Layout(type=%s)" % repr(self.__class__.__name__.lower())

    # Debug mode:
    """
    def draw(self):
        rect(0, 0, self.width, self.height, fill=None, stroke=(0,0.5,1,1))
    """


# -- Layout: Labeled ----------------------------------------------------------

class Labeled(Layout):
    """A layout where each control has an associated text label."""

    def __init__(self, controls=[], x=0, y=0, **kwargs):
        Layout.__init__(self, controls=[], x=x, y=y, **kwargs)
        self.controls = []
        self.captions = []
        self.extend(controls)

    def insert(self, i, control, caption=""):
        """Insert a new control to the layout, with an associated caption.

        Each control will be drawn in a new row.

        """
        self.controls.insert(i, control)
        self.captions.insert(i, Label(caption.upper(),
            fontsize=theme["fontsize"] * 0.8,
            fill=theme["text"].rgb + (theme["text"].a * 0.8,)))
        Layout.insert(self, i, self.controls[i])
        Layout.insert(self, i, self.captions[i])

    def append(self, control, caption=""):
        self.insert(len(self) / 2, control, caption)

    def extend(self, controls):
        for control in controls:
            if isinstance(control, tuple):
                self.append(*control)
            else:
                self.append(control, "")

    def remove(self, control):
        self.pop(self.controls.index(control))

    def pop(self, i):
        self.captions.pop(i)
        return self.controls.pop(i)


# -- Layout: Rows -------------------------------------------------------------

class VBox(Labeled):

    def __init__(self, controls=[], x=0, y=0, width=125, **kwargs):
        """A layout where each control appears on a new line.

        Each control has an associated text caption, displayed to the left of
        the control. The given width defines the desired width for each
        control.

        """
        Labeled.__init__(self, controls, x=x, y=y, **kwargs)
        self._maxwidth = width

    def apply(self):
        """Adjust the position and width of all the controls in the layout:

        - each control is placed next to its caption, with spacing in between,
        - each caption is aligned to the right, and centered vertically,
        - the width of all Label, Button, Slider, Field controls is evened out.

        """
        mw = self._maxwidth
        for control in self.controls:
            if isinstance(control, Layout):
                # Child containers in the layout can be wider than the desired
                # width. Adjusting mw at the start will make controls wider to
                # line out with the total width, adjusting it at the end would
                # just ensure that the layout is wide enough.
                mw = max(mw, control.width)

        w1 = max(caption.width for caption in self.captions)
        w2 = max(control.width for control in self.controls)
        w2 = min(w2, mw)
        dx = 0
        dy = 0

        for caption, control in reversed(zip(self.captions, self.controls)):
            if (isinstance(control, Layout)
                    and control.height > caption.height * 2):
                # valign top.
                caption.y = dy + control.height - caption.height

            if isinstance(control, (Label, Button, Slider, Field)):
                control._set_width(mw)
                control._pack()

            # halign right.
            caption.x = dx + w1 - caption.width
            control.x = dx + w1 + (w1 > 0 and self.spacing)
            # valign center.
            caption.y = dy + 0.5 * (control.height - caption.height)
            control.y = dy
            dy += max(caption.height, control.height) + self.spacing

        self.width = w1 + max(w2, mw) + (w1 > 0 and self.spacing)
        self.height = dy - self.spacing


class HBox(Labeled):
    """A layout where each control appears in a new column.

    Each control has an associated text caption, displayed on top of the
    control. The given width defines the desired width for each control.

    """
    def __init__(self, controls=[], x=0, y=0, width=125, align=CENTER,
                 **kwargs):
        Labeled.__init__(self, controls, x=x, y=y, **kwargs)
        self._maxwidth = width
        self._align = align

    def apply(self):
        """Adjust the position and width of all the controls in the layout.

        - each control is placed centrally below its caption, with spacing in
          between
        - the width of all Label, Button, Slider, Field controls is evened out.

        """
        mw = self._maxwidth
        da = {TOP: 1.0, BOTTOM: 0.0, CENTER: 0.5}.get(self._align, 0.5)
        h1 = max(control.height for control in self.controls)
        h2 = max(caption.height for caption in self.captions)
        dx = 0
        dy = 0
        for caption, control in zip(self.captions, self.controls):
            if isinstance(control, (Label, Button, Slider, Field)):
                control._set_width(mw)
                control._pack()
            # halign center
            caption.x = dx + 0.5 * max(control.width - caption.width, 0)
            control.x = dx + 0.5 * max(caption.width - control.width, 0)
            caption.y = dy + h1 + (h2 > 0 and self.spacing)
            # valign center
            control.y = dy + da * (h1 - control.height)
            dx += max(caption.width, control.width) + self.spacing
        self.width = dx - self.spacing
        self.height = h1 + h2 + (h2 > 0 and self.spacing)


Row = HBox
Rows = VBox
