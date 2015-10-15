# == CONTEXT ==================================================================
# 2D NodeBox API in OpenGL.
# Authors: Tom De Smedt, Frederik De Bleser
# License: BSD (see LICENSE.txt for details).
# Copyright (c) 2008-2012 City In A Bottle (cityinabottle.org)
# http://cityinabottle.org/nodebox

# All graphics are drawn directly to the screen.
# No scenegraph is kept for obvious performance reasons
# (therefore, no canvas._grobs as in NodeBox).

# Debugging must be switched on or off before other modules are imported.

from __future__ import absolute_import, print_function

import pyglet
pyglet.options['debug_gl'] = False

try:
    import cPickle as pickle
except ImportError:
    import pickle

from datetime import datetime
from glob import glob
from math import cos, sin, pi, floor
from os import remove
from os.path import dirname, join, normpath
from random import choice, shuffle, random as rnd
from sys import getrefcount, stderr
from time import time
from types import FunctionType, MethodType

from pyglet.gl import *  # noqa

from . import geometry
from .bezier import *  # noqa
from .caching import *  # noqa
from .color import *  # noqa
from .drawing import *  # noqa
from .image import *  # noqa
from .primitives import *  # noqa
from .shader import *  # noqa
from .state import global_state as _g, state_mixin


try:
    integer_types = (int, long)
    range = xrange
except NameError:
    integer_types = (int,)

# OpenGL version, e.g. "2.0 NVIDIA-1.5.48".
OPENGL = pyglet.gl.gl_info.get_version()

# The default fill is black.
fill(0)

# -- BEZIER EDITOR ------------------------------------------------------------

EQUIDISTANT = "equidistant"
# Drag pt1.ctrl2, pt2.ctrl1 or both simultaneously?
IN, OUT, BOTH = "in", "out", "both"

class BezierEditor(object):

    def __init__(self, path):
        self.path = path

    def _nextpoint(self, pt):
        i = self.path.index(pt) # BezierPath caches this operation.
        return i < len(self.path)-1 and self.path[i+1] or None

    def translate(self, pt, x=0, y=0, h1=(0,0), h2=(0,0)):
        """Translates the point and its control handles by (x,y).

        Translates the incoming handle by h1 and the outgoing handle by h2.

        """
        pt1, pt2 = pt, self._nextpoint(pt)
        pt1.x += x
        pt1.y += y
        pt1.ctrl2.x += x + h1[0]
        pt1.ctrl2.y += y + h1[1]
        if pt2 is not None:
            pt2.ctrl1.x += x + (pt2.cmd == CURVETO and h2[0] or 0)
            pt2.ctrl1.y += y + (pt2.cmd == CURVETO and h2[1] or 0)

    def rotate(self, pt, angle, handle=BOTH):
        """Rotates the point control handles by the given angle."""
        pt1, pt2 = pt, self._nextpoint(pt)
        if handle == BOTH or handle == IN:
            pt1.ctrl2.x, pt1.ctrl2.y = geometry.rotate(pt1.ctrl2.x, pt1.ctrl2.y, pt1.x, pt1.y, angle)
        if handle == BOTH or handle == OUT and pt2 is not None and pt2.cmd == CURVETO:
            pt2.ctrl1.x, pt2.ctrl1.y = geometry.rotate(pt2.ctrl1.x, pt2.ctrl1.y, pt1.x, pt1.y, angle)

    def scale(self, pt, v, handle=BOTH):
        """Scales the point control handles by the given factor."""
        pt1, pt2 = pt, self._nextpoint(pt)
        if handle == BOTH or handle == IN:
            pt1.ctrl2.x, pt1.ctrl2.y = linepoint(v, pt1.x, pt1.y, pt1.ctrl2.x, pt1.ctrl2.y)
        if handle == BOTH or handle == OUT and pt2 is not None and pt2.cmd == CURVETO:
            pt2.ctrl1.x, pt2.ctrl1.y = linepoint(v, pt1.x, pt1.y, pt2.ctrl1.x, pt2.ctrl1.y)

    def smooth(self, pt, mode=None, handle=BOTH):
        pt1, pt2, i = pt, self._nextpoint(pt), self.path.index(pt)
        if pt2 is None:
            return
        if pt1.cmd == pt2.cmd == CURVETO:
            if mode == EQUIDISTANT:
                d1 = d2 = 0.5 * (
                     geometry.distance(pt1.x, pt1.y, pt1.ctrl2.x, pt1.ctrl2.y) + \
                     geometry.distance(pt1.x, pt1.y, pt2.ctrl1.x, pt2.ctrl1.y))
            else:
                d1 = geometry.distance(pt1.x, pt1.y, pt1.ctrl2.x, pt1.ctrl2.y)
                d2 = geometry.distance(pt1.x, pt1.y, pt2.ctrl1.x, pt2.ctrl1.y)
            if handle == IN:
                a = geometry.angle(pt1.x, pt1.y, pt1.ctrl2.x, pt1.ctrl2.y)
            if handle == OUT:
                a = geometry.angle(pt2.ctrl1.x, pt2.ctrl1.y, pt1.x, pt1.y)
            if handle == BOTH:
                a = geometry.angle(pt2.ctrl1.x, pt2.ctrl1.y, pt1.ctrl2.x, pt1.ctrl2.y)
            pt1.ctrl2.x, pt1.ctrl2.y = geometry.coordinates(pt1.x, pt1.y, d1, a)
            pt2.ctrl1.x, pt2.ctrl1.y = geometry.coordinates(pt1.x, pt1.y, d2, a-180)
        elif pt1.cmd == CURVETO and pt2.cmd == LINETO:
            d = mode == EQUIDISTANT and \
                geometry.distance(pt1.x, pt1.y, pt2.x, pt2.y) or \
                geometry.distance(pt1.x, pt1.y, pt1.ctrl2.x, pt1.ctrl2.y)
            a = geometry.angle(pt1.x, pt1.y, pt2.x, pt2.y)
            pt1.ctrl2.x, pt1.ctrl2.y = geometry.coordinates(pt1.x, pt1.y, d, a-180)
        elif pt1.cmd == LINETO and pt2.cmd == CURVETO and i > 0:
            d = mode == EQUIDISTANT and \
                geometry.distance(pt1.x, pt1.y, self.path[i-1].x, self.path[i-1].y) or \
                geometry.distance(pt1.x, pt1.y, pt2.ctrl1.x, pt2.ctrl1.y)
            a = geometry.angle(self.path[i-1].x, self.path[i-1].y, pt1.x, pt1.y)
            pt2.ctrl1.x, pt2.ctrl1.y = geometry.coordinates(pt1.x, pt1.y, d, a)


# -- POINT ANGLES -------------------------------------------------------------

def directed(points):
    """Return iterator yielding (angle, point)-tuples for given list of points.

    The angle represents the direction of the point on the path. This works
    with BezierPath, Bezierpath.points, [pt1, pt2, pt2, ...]

    For example:
        for a, pt in directed(path.points(30)):
            push()
            translate(pt.x, pt.y)
            rotate(a)
            arrow(0, 0, 10)
            pop()

    This is useful if you want to have shapes following a path. To put text on
    a path, rotate the angle by +-90 to get the normal (i.e. perpendicular).

    """
    p = list(points)
    n = len(p)

    for i, pt in enumerate(p):
        if 0 < i < n-1 and pt.__dict__.get("_cmd") == CURVETO:
            # For a point on a curve, the control handle gives the best direction.
            # For PathElement (fixed point in BezierPath), ctrl2 tells us how the curve arrives.
            # For DynamicPathElement (returnd from BezierPath.point()), ctrl1 tell how the curve arrives.
            ctrl = isinstance(pt, DynamicPathElement) and pt.ctrl1 or pt.ctrl2
            angle = geometry.angle(ctrl.x, ctrl.y, pt.x, pt.y)
        elif 0 < i < n-1 and pt.__dict__.get("_cmd") == LINETO and p[i-1].__dict__.get("_cmd") == CURVETO:
            # For a point on a line preceded by a curve, look ahead gives better results.
            angle = geometry.angle(pt.x, pt.y, p[i+1].x, p[i+1].y)
        elif i == 0 and isinstance(points, BezierPath):
            # For the first point in a BezierPath, we can calculate a next point very close by.
            pt1 = points.point(0.001)
            angle = geometry.angle(pt.x, pt.y, pt1.x, pt1.y)
        elif i == n-1 and isinstance(points, BezierPath):
            # For the last point in a BezierPath, we can calculate a previous point very close by.
            pt0 = points.point(0.999)
            angle = geometry.angle(pt0.x, pt0.y, pt.x, pt.y)
        elif i == n-1 and isinstance(pt, DynamicPathElement) and pt.ctrl1.x != pt.x or pt.ctrl1.y != pt.y:
            # For the last point in BezierPath.points(), use incoming handle (ctrl1) for curves.
            angle = geometry.angle(pt.ctrl1.x, pt.ctrl1.y, pt.x, pt.y)
        elif 0 < i:
            # For any point, look back gives a good result, if enough points are given.
            angle = geometry.angle(p[i-1].x, p[i-1].y, pt.x, pt.y)
        elif i < n-1:
            # For the first point, the best (only) guess is the location of the next point.
            angle = geometry.angle(pt.x, pt.y, p[i+1].x, p[i+1].y)
        else:
            angle = 0
        yield angle, pt


# -- CLIPPING PATH ------------------------------------------------------------

class ClippingMask(object):
    def draw(self, fill=(0,0,0,1), stroke=None):
        pass


def beginclip(path):
    """Enable the given BezierPath (or ClippingMask) as a clipping mask.

    Drawing commands between beginclip() and endclip() are constrained to the
    shape of the path.

    """
    # Enable the stencil buffer to limit the area of rendering (stenciling).
    glClear(GL_STENCIL_BUFFER_BIT)
    glEnable(GL_STENCIL_TEST)
    glStencilFunc(GL_NOTEQUAL, 0, 0)
    glStencilOp(GL_INCR, GL_INCR, GL_INCR)
    # Shouldn't depth testing be disabled when stencilling?
    # In any case, if it is, transparency doesn't work.
    #glDisable(GL_DEPTH_TEST)
    path.draw(fill=(0,0,0,1), stroke=None) # Disregard color settings; always use a black mask.
    #glEnable(GL_DEPTH_TEST)
    glStencilFunc(GL_EQUAL, 1, 1)
    glStencilOp(GL_KEEP, GL_KEEP, GL_KEEP)

def endclip():
    glDisable(GL_STENCIL_TEST)


# -- SUPERSHAPE ---------------------------------------------------------------

def supershape(x, y, width, height, m, n1, n2, n3, points=100, percentage=1.0,
               range_=2*pi, **kwargs):
    """Return a BezierPath constructed using the superformula.

    This formula can be used to describe many complex shapes and curves that
    are found in nature.

    """
    path = BezierPath()
    first = True

    for i in range(points):
        if i <= points * percentage:
            dx, dy = geometry.superformula(m, n1, n2, n3, i * range_ / points)
            dx, dy = dx*width/2 + x, dy*height/2 + y

            if first is True:
                path.moveto(dx, dy); first=False
            else:
                path.lineto(dx, dy)

    path.closepath()

    if kwargs.get("draw", True):
        path.draw(**kwargs)

    return path


#--- ANIMATION ----------------------------------------------------------------
# A sequence of images displayed in a loop.
# Useful for storing pre-rendered effect frames like explosions etc.

class Animation(list):

    def __init__(self, images=[], duration=None, loop=False, **kwargs):
        """Constructs an animation loop from the given image frames.

        The duration specifies the time for the entire animation to run.
        Animations are useful to cache effects like explosions, that have for
        example been prepared in an offscreen buffer.

        """
        list.__init__(self, list(images))
        self.duration = duration # Duration of the entire animation.
        self.loop = loop     # Loop from last frame to first frame?
        self._i = -1       # Frame counter.
        self._t = Transition(0, interpolation=kwargs.get("interpolation", LINEAR))

    def copy(self, **kwargs):
        return Animation(self,
              duration = kwargs.get("duration", self.duration),
                  loop = kwargs.get("loop", self.loop),
         interpolation = self._t._interpolation)

    def update(self):
        if self.duration is not None:
            # With a duration,
            # skip to a next frame so that the entire animation takes the given time.
            if self._i < 0 or self.loop and self._i == len(self)-1:
                self._t.set(0, 0)
                self._t.update()
                self._t.set(len(self)-1, self.duration)
            self._t.update()
            self._i = int(self._t.current)
        else:
            # Without a duration,
            # Animation.update() simply moves to the next frame.
            if self._i < 0 or self.loop and self._i == len(self)-1:
                self._i = -1
            self._i = min(self._i+1, len(self)-1)

    @property
    def frames(self):
        return self

    @property
    def frame(self):
        # Yields the current frame Image (or None).
        try: return self[self._i]
        except:
            return None

    @property
    def done(self):
        # Yields True when the animation has stopped (or hasn't started).
        return self.loop is False and self._i == len(self)-1

    def draw(self, *args, **kwargs):
        kwargs['alpha'] = kwargs.get('alpha', 1.0) * _g.alpha
        if not self.done:
            image(self.frame, *args, **kwargs)

    def __repr__(self):
        return "%s(frames=%i, duration=%s)" % (
            self.__class__.__name__, len(self), repr(self.duration))


animation = Animation


#--- OFFSCREEN RENDERING ------------------------------------------------------
# Offscreen buffers can be used to render images from paths etc.
# or to apply filters on images before drawing them to the screen.
# There are several ways to draw offscreen:
#
# - render(img, filter): applies the given filter to the image and returns it.
# - procedural(function, width, height): execute the drawing commands in
#   function inside an image.
# - Create your own subclass of OffscreenBuffer with a draw() method:
#   class MyBuffer(OffscreenBuffer):
#       def draw(self): pass
# - Define drawing commands between OffscreenBuffer.push() and pop():
#   b = MyBuffer()
#   b.push()
#   # drawing commands
#   b.pop()
#   img = Image(b.render())
#
# The shader.py module already defines several filters that use an offscreen
# buffer, for example:
# blur(), adjust(), multiply(), twirl(), ...
#
# The less you change about an offscreen buffer, the faster it runs.
# This includes switching it on and off and changing its size.


# =============================================================================

#--- FONT ---------------------------------------------------------------------

# Font weight
NORMAL = "normal"
BOLD = "bold"
ITALIC = "italic"

# Text alignment
LEFT = "left"
RIGHT = "right"
CENTER = "center"


def install_font(ttf):
    """Load the given TrueType font from file, and returns True on success."""
    try:
        pyglet.font.add_file(ttf)
        return True
    except:
        # This might fail with Carbon on 64-bit Mac systems.
        # Fonts can be installed on the system manually if this is the case.
        return False


# Load the platform-independent fonts shipped with NodeBox.
# The default font is Droid (licensed under Apache 2.0).
try:
    for f in glob(path.join(path.dirname(__file__), "..", "font", "*")):
        install_font(f)
    DEFAULT_FONT = "Droid Sans"
except:
    DEFAULT_FONT = "Arial"


_fonts = []             # Custom fonts loaded from file.
_fontname = DEFAULT_FONT   # Current state font name.
_fontsize = 12             # Current state font size.
_fontweight = [False, False] # Current state font weight (bold, italic).
_lineheight = 1.0            # Current state text lineheight.
_align = LEFT           # Current state text alignment (LEFT/RIGHT/CENTER).


def font(fontname=None, fontsize=None, fontweight=None, file=None):
    """Set the current font and/or fontsize.

    If a filename is also given, loads the fontname from the given font file.

    """
    global _fontname, _fontsize
    if file is not None and file not in _fonts:
        _fonts.append(file); install_font(file)
    if fontname is not None:
        _fontname = fontname
    if fontsize is not None:
        _fontsize = fontsize
    if fontweight is not None:
        _fontweight_(fontweight) # _fontweight_() is just an alias for fontweight().
    return _fontname


def fontname(name=None):
    """Setsthe current font used when drawing text."""
    global _fontname
    if name is not None:
        _fontname = name
    return _fontname


def fontsize(size=None):
    """Set the current fontsize in points."""
    global _fontsize
    if size is not None:
        _fontsize = size
    return _fontsize


def fontweight(*args, **kwargs):
    """Sets the current font weight.

    You can supply NORMAL, BOLD and/or ITALIC or set named parameters bold=True
    and/or italic=True.

    """
    global _fontweight

    if len(args) == 1 and isinstance(args, (list, tuple)):
        args = args[0]

    if NORMAL in args:
        _fontweight = [False, False]

    if BOLD in args or kwargs.get(BOLD):
        _fontweight[0] = True

    if ITALIC in args or kwargs.get(ITALIC):
        _fontweight[1] = True

    return _fontweight

_fontweight_ = fontweight


def lineheight(size=None):
    """Set the vertical spacing between lines of text.

    The given size is a relative value: lineheight 1.2 for fontsize 10 means
    12.

    """
    global _lineheight
    if size is not None:
        _lineheight = size
    return _lineheight


def align(mode=None):
    """ Sets the alignment of text paragrapgs (LEFT, RIGHT or CENTER).
    """
    global _align
    if mode is not None:
        _align = mode
    return _align


# -- FONT MIXIN ---------------------------------------------------------------
# The text() command has optional parameters font, fontsize, fontweight, bold,
# italic, lineheight and align.

def font_mixin(**kwargs):
    fontname = kwargs.get("fontname", kwargs.get("font", _fontname))
    fontsize = kwargs.get("fontsize", _fontsize)
    bold = kwargs.get("bold", BOLD in kwargs.get("fontweight", "") or _fontweight[0])
    italic = kwargs.get("italic", ITALIC in kwargs.get("fontweight", "") or _fontweight[1])
    lineheight = kwargs.get("lineheight", _lineheight)
    align = kwargs.get("align", _align)
    return (fontname, fontsize, bold, italic, lineheight, align)


# -- TEXT ---------------------------------------------------------------------
# Text is cached for performance.
# For optimal performance, texts should be created once (not every frame) and left unmodified.
# Dynamic texts use a cache of recycled Text objects.

# pyglet.text.Label leaks memory when deleted, because its old batch continues to reference
# loaded font/fontsize/bold/italic glyphs.
# Adding all labels to our own batch remedies this.
_label_batch = pyglet.graphics.Batch()

def label(str="", width=None, height=None, **kwargs):
    """Return a drawable pyglet.text.Label object from the given string.

    Optional arguments include: font, fontsize, bold, italic, align,
    lineheight, fill. If these are omitted the current state is used.

    """
    fontname, fontsize, bold, italic, lineheight, align = font_mixin(**kwargs)
    fill, stroke, strokewidth, strokestyle = state_mixin(**kwargs)
    fill = fill is None and (0,0,0,0) or fill
    # We use begin_update() so that the TextLayout doesn't refresh on each update.
    # FormattedDocument allows individual styling of characters - see Text.style().
    label = pyglet.text.Label(batch=_label_batch)
    label.begin_update()
    label.document = pyglet.text.document.FormattedDocument(str or " ")
    label.width = width
    label.height = height
    label.font_name = fontname
    label.font_size = fontsize
    label.bold = bold
    label.italic = italic
    label.multiline = True
    label.anchor_y = "bottom"
    label.set_style("align", align)
    label.set_style("line_spacing", lineheight * fontsize)
    label.color = [int(ch*255) for ch in fill]
    if str == "":
        # Empty string "" does not set properties so we used " " first.
        label.text = str
    label.end_update()
    return label


class Text(object):
    """A formatted string of text that can be drawn at a given position."""

    def __init__(self, str, x=0, y=0, width=None, height=None, **kwargs):
        """Create a tex instance with given position and size.

        Text has the following properties:

            text, x, y, width, height, font, fontsize, bold, italic,
            lineheight, align, fill.

        Individual character ranges can be styled with Text.style().

        """
        if width is None:
            # Supplying a string with "\n" characters will crash if no width is
            # given. On the outside it appears as None but inside we use a very
            # large number.
            width = geometry.INFINITE
            a, kwargs["align"] = kwargs.get("align", _align), LEFT
        else:
            a = None

        self.__dict__["x"] = x
        self.__dict__["y"] = y
        self.__dict__["_label"] = label(str, width, height, **kwargs)
        self.__dict__["_dirty"] = False
        self.__dict__["_align"] = a
        self.__dict__["_fill"] = None

    @property
    def xy(self):
        return (self.x, self.y)

    @xy.setter
    def xy(self, v):
        self.x = v[0]
        self.y = v[1]

    @property
    def size(self):
        return (self.width, self.height)

    @size.setter
    def size(self, wh):
        self.width = wh[0]
        self.height = wh[1]

    def __getattr__(self, k):
        if k in self.__dict__:
            return self.__dict__[k]
        elif k in ("text", "height", "bold", "italic"):
            return getattr(self._label, k)
        elif k == "string":
            return self._label.text
        elif k == "width":
            if self._label.width != geometry.INFINITE:
                return self._label.width
        elif k in ("font", "fontname"):
            return self._label.font_name
        elif k == "fontsize":
            return self._label.font_size
        elif k == "fontweight":
            return ((None, BOLD)[self._label.bold], (None, ITALIC)[self._label.italic])
        elif k == "lineheight":
            return self._label.get_style("line_spacing") / (self.fontsize or 1)
        elif k == "align":
            if not self._align:
                self._align = self._label.get_style(k)

            return self._align
        elif k == "fill":
            if not self._fill:
                self._fill = Color([ch/255.0 for ch in self._label.color])

            return self._fill
        else:
            raise AttributeError("'Text' object has no attribute '%s'" % k)

    def __setattr__(self, k, v):
        if k in self.__dict__:
            self.__dict__[k] = v; return

        # Setting properties other than x and y
        # requires the label's layout to be updated.
        self.__dict__["_dirty"] = True
        self._label.begin_update()

        if k in ("text", "height", "bold", "italic"):
            setattr(self._label, k, v)
        elif k == "string":
            self._label.text = v
        elif k == "width":
            self._label.width = v is None and geometry.INFINITE or v
        elif k in ("font", "fontname"):
            self._label.font_name = v
        elif k == "fontsize":
            self._label.font_size = v
        elif k == "fontweight":
            self._label.bold, self._label.italic = BOLD in v, ITALIC in v
        elif k == "lineheight":
            self._label.set_style("line_spacing", v * (self.fontsize or 1))
        elif k == "align":
            self._align = v
            self._label.set_style(k, LEFT if self._label.width == geometry.INFINITE else v)
        elif k == "fill":
            self._fill = v
            self._label.color = [int(255 * ch) for ch in self._fill or (0, 0, 0, 0)]
        else:
            raise AttributeError("'Text' object has no attribute '%s'" % k)

    def _update(self):
        # Called from Text.draw(), Text.copy() and Text.metrics.
        # Ensures that all color changes have been reflected in Text._label.
        # If necessary, recalculates the label's layout (in end_update()).
        if hasattr(self._fill, "_dirty") and self._fill._dirty:
            self.fill = self._fill
            self._fill._dirty = False

        if self._dirty:
            self._label.end_update()
            self._dirty = False

    @property
    def path(self):
        raise NotImplementedError

    @property
    def metrics(self):
        """Yield a (width, height)-tuple of the actual text content."""
        self._update()
        return self._label.content_width, self._label.content_height

    def draw(self, x=None, y=None):
        """Draw the text."""
        # Given parameters override Text attributes.
        if x is None:
            x = self.x

        if y is None:
            y = self.y

        # Fontsize is rounded, and fontsize 0 will output a default font.
        # Therefore, we don't draw text with a fontsize smaller than 0.5.
        if self._label.font_size >= 0.5:
            glPushMatrix()
            glTranslatef(x, y, 0)
            self._update()
            self._label.draw()
            glPopMatrix()

    def copy(self):
        self._update()
        txt = Text(self.text, self.x, self.y, self.width, self.height,
            fontname=self.fontname, fontsize=self.fontsize, bold=self.bold,
            italic=self.italic, lineheight=self.lineheight, align=self.align,
            fill=self.fill)
        # The individual character styling is retrieved from Label.document._style_runs.
        # Traverse it and set the styles in the new text.
        txt._label.begin_update()

        for k in self._label.document._style_runs:
            for i, j, v in self._label.document._style_runs[k]:
                txt.style(i,j, **{k:v})

        txt._label.end_update()
        return txt

    def style(self, i, j, **kwargs):
        """Defines the styling for a range of characters in the text.

        Valid arguments can include: font, fontsize, bold, italic, lineheight,
        align, fill.

        For example: text.style(0, 10, bold=True, fill=color(1,0,0))

        """
        attributes = {}
        for k, v in kwargs.items():
            if k in ("font", "fontname"):
                attributes["font_name"] = v
            elif k == "fontsize":
                attributes["font_size"] = v
            elif k in ("bold", "italic", "align"):
                attributes[k] = v
            elif k == "fontweight":
                attributes.setdefault("bold", BOLD in v)
                attributes.setdefault("italic", ITALIC in v)
            elif k == "lineheight":
                attributes["line_spacing"] = v * self._label.font_size
            elif k == "fill":
                attributes["color"] = [int(ch*255) for ch in v]
            else:
                attributes[k] = v

        self._dirty = True
        self._label.begin_update()
        self._label.document.set_style(i, j, attributes)

    def __len__(self):
        return len(self.text)

    def __del__(self):
        if hasattr(self, "_label") and self._label:
            self._label.delete()


_TEXT_CACHE = 200
_text_cache = {}
_text_queue = []


def text(str, x=None, y=None, width=None, height=None, draw=True, **kwargs):
    """Draw the string at the given position, with the current font().

    Lines of text will span the given width before breaking to the next line.
    The text will be displayed with the current state font(), fontsize(),
    fontweight(), etc. When the given text is a Text object, the state will not
    be applied.

    """
    if all((isinstance(str, Text), width is None, height is None, not kwargs)):
        txt = str
    else:
        # If the given text is not a Text object, create one on the fly.
        # Dynamic Text objects are cached by (font, fontsize, bold, italic),
        # and those that are no longer referenced by the user are recycled.
        # Changing Text properties is still faster than creating a new Text.
        # The cache has a limited size (200), so the oldest Text objects are deleted.
        fontname, fontsize, bold, italic, lineheight, align = font_mixin(**kwargs)
        fill, stroke, strokewidth, strokestyle = state_mixin(**kwargs)
        id = (fontname, int(fontsize), bold, italic)
        recycled = False

        if id in _text_cache:
            for txt in _text_cache[id]:
                # Reference count 3 => Python, _text_cache[id], txt.
                # No other variables are referencing the text, so we can recycle it.
                if getrefcount(txt) == 3:
                    txt.text = str
                    txt.x = x or 0
                    txt.y = y or 0
                    txt.width = width
                    txt.height = height
                    txt.lineheight = lineheight
                    txt.align = align
                    txt.fill = fill
                    recycled = True
                    break

        if not recycled:
            txt = Text(str, x or 0, y or 0, width, height, **kwargs)
            _text_cache.setdefault(id, []).append(txt)
            _text_queue.insert(0, id)

            for id in reversed(_text_queue[_TEXT_CACHE:]):
                del _text_cache[id][0]
                del _text_queue[-1]

    if draw:
        txt.draw(x, y)

    return txt


def textwidth(txt, **kwargs):
    """Return the width of the given text."""
    if not isinstance(txt, Text) or len(kwargs) > 0:
        kwargs["draw"] = False
        txt = text(txt, 0, 0, **kwargs)

    return txt.metrics[0]


def textheight(txt, width=None, **kwargs):
    """Return the height of the given text."""
    if not isinstance(txt, Text) or len(kwargs) > 0 or width != txt.width:
        kwargs["draw"] = False
        txt = text(txt, 0, 0, width=width, **kwargs)

    return txt.metrics[1]


def textmetrics(txt, width=None, **kwargs):
    """Return a (width, height)-tuple for the given text."""
    if not isinstance(txt, Text) or len(kwargs) > 0 or width != txt.width:
        kwargs["draw"] = False
        txt = text(txt, 0, 0, width=width, **kwargs)

    return txt.metrics


#--- TEXTPATH -----------------------------------------------------------------

class GlyphPathError(Exception):
    pass

glyphs = {}

try:
    # Load cached font glyph path information from nodebox/font/glyph.p.
    # By default, it has glyph path info for Droid Sans, Droid Sans Mono,
    # Droid Serif.
    glyphs = normpath(join(dirname(__file__), "..", "font", "glyph.p"))
    glyphs = pickle.load(open(glyphs, 'rb'))
except Exception as exc:
    print("Error reading picked font glyph metrics: %s" % exc, file=stderr)

def textpath(string, x=0, y=0, **kwargs):
    """Returns a BezierPath from the given text string.

    The fontname, fontsize and fontweight can be given as optional parameters,
        width, height, lineheight and align are ignored.

    Only works with ASCII characters in the default fonts (Droid Sans, Droid
    Sans Mono, Droid Serif, Arial). See nodebox/font/glyph.py on how to
    activate other fonts.

    """
    fontname, fontsize, bold, italic, lineheight, align = font_mixin(**kwargs)
    w = bold and italic and "bold italic" or bold and "bold" or italic and "italic" or "normal"
    p = BezierPath()
    f = fontsize / 1000.0

    for ch in string:
        try:
            glyph = glyphs[fontname][w][ch]
        except KeyError:
            raise GlyphPathError("no glyph path information for %s %s '%s'" %
                                 (w, fontname, ch))

        for pt in glyph:
            if pt[0] == MOVETO:
                p.moveto(x+pt[1]*f, y-pt[2]*f)
            elif pt[0] == LINETO:
                p.lineto(x+pt[1]*f, y-pt[2]*f)
            elif pt[0] == CURVETO:
                p.curveto(x+pt[3]*f, y-pt[4]*f, x+pt[5]*f, y-pt[6]*f, x+pt[1]*f, y-pt[2]*f)
            elif pt[0] == CLOSE:
                p.closepath()

        x += textwidth(ch, font=fontname, fontsize=fontsize, bold=bold, italic=italic)

    return p


# =============================================================================

# -- UTILITIES ----------------------------------------------------------------

_RANDOM_MAP = [90.0, 9.00, 4.00, 2.33, 1.50, 1.00, 0.66, 0.43, 0.25, 0.11, 0.01]
def _rnd_exp(bias=0.5):
    bias = max(0, min(bias, 1)) * 10
    i = int(floor(bias))             # bias*10 => index in the _map curve.
    n = _RANDOM_MAP[i]               # If bias is 0.3, rnd()**2.33 will average 0.3.

    if bias < 10:
        n += (_RANDOM_MAP[i + 1] - n) * (bias - i)

    return n


def random(v1=1.0, v2=None, bias=None):
    """Return a number between v1 and v2, including v1 but not v2.

    The bias (0.0-1.0) represents preference towards lower or higher numbers.

    """
    if v2 is None:
        v1, v2 = 0, v1

    if bias is None:
        r = rnd()
    else:
        r = rnd() ** _rnd_exp(bias)

    x = r * (v2 - v1) + v1

    if isinstance(v1, int) and isinstance(v2, int):
        x = int(x)

    return x


def grid(cols, rows, colwidth=1, rowheight=1, shuffled=False):
    """Yield (x,y)-tuples for the given number of rows and columns.

    The space between each point is determined by colwidth and colheight.

    """
    rows = list(range(int(rows)))
    cols = list(range(int(cols)))

    if shuffled:
        shuffle(rows)
        shuffle(cols)

    for y in rows:
        for x in cols:
            yield (x * colwidth, y * rowheight)

def files(path="*"):
    """Return a list of files found at the given path."""
    return glob(path)


#==============================================================================

#--- PROTOTYPE ----------------------------------------------------------------

class Prototype(object):
    """A base class that allows on-the-fly extension.

    This means that external functions can be bound to it as methods, and
    properties set at runtime are copied correctly.

    Prototype can handle:

    - functions (these become class methods),
    - immutable types (str, unicode, int, long, float, bool),
    - lists, tuples and dictionaries of immutable types,
    - objects with a copy() method.

    """
    def __init__(self):
        self._dynamic = {}

    def _deepcopy(self, value):
        if isinstance(value, FunctionType):
            return MethodType(value, self)
        elif hasattr(value, "copy"):
            return value.copy()
        elif isinstance(value, (list, tuple)):
            return [self._deepcopy(x) for x in value]
        elif isinstance(value, dict):
            return dict([(k, self._deepcopy(v)) for k, v in value.items()])
        elif isinstance(value, (str, float, bool) + integer_types):
            return value
        else:
            # Biggest problem here is how to find/relink circular references.
            raise TypeError("Prototype can't bind %s." % value.__class__)

    def _bind(self, key, value):
        """Adds a new method or property to the prototype.

        For methods, the given function is expected to take the object (i.e.
        self) as first parameter.

        For properties, values can be: list, tuple, dict, str, unicode, int,
        long, float, bool, or an object with a copy() method.

        For example, we can define a Layer's custom draw() method in two ways:

        - By subclassing:

            class MyLayer(Layer):
                def draw(layer):
                    pass

            layer = MyLayer()
            layer.draw()

        - By function binding:

            def my_draw(layer):
                pass

            layer = Layer()
            layer._bind("draw", my_draw)
            layer.draw()

        """
        self._dynamic[key] = value
        object.__setattr__(self, key, self._deepcopy(value))

    def set_method(self, function, name=None):
        """Create dynamic method (with the given name) from the given function.
        """
        if not name:
            name = function.__name__

        self._bind(name, function)

    def set_property(self, key, value):
        """Add a property to the prototype.

        Using this method ensures that dynamic properties are copied correctly
        - see inherit().

        """
        self._bind(key, value)

    def inherit(self, prototype):
        """Inherit all the dynamic properties and methods of another prototype.
        """
        for k, v in prototype._dynamic.items():
            self._bind(k,v)

# =============================================================================

# -- EVENT HANDLER ------------------------------------------------------------

class EventHandler(object):

    def __init__(self):
        # Use __dict__ directly so we can do multiple inheritance in
        # combination with Prototype:
        self.__dict__["enabled"] = True  # Receive events from the canvas?
        self.__dict__["focus"] = False # True when this object receives the focus.
        self.__dict__["pressed"] = False # True when the mouse is pressed on this object.
        self.__dict__["dragged"] = False # True when the mouse is dragged on this object.
        self.__dict__["_queue"] = []

    def on_mouse_enter(self, mouse):
        pass

    def on_mouse_leave(self, mouse):
        pass

    def on_mouse_motion(self, mouse):
        pass

    def on_mouse_press(self, mouse):
        pass

    def on_mouse_release(self, mouse):
        pass

    def on_mouse_drag(self, mouse):
        pass

    def on_mouse_scroll(self, mouse):
        pass

    def on_key_press(self, keys):
        pass

    def on_key_release(self, keys):
        pass

    # Instead of calling an event directly it could be queued, e.g.
    # layer.queue_event(layer.on_mouse_press, canvas.mouse).
    # layer.process_events() can then be called whenever desired, e.g. after
    # the canvas has been drawn so that events can contain drawing commands.
    def queue_event(self, event, *args):
        self._queue.append((event, args))
    def process_events(self):
        for event, args in self._queue:
            event(*args)
        self._queue = []

    # Note: there is no event propagation.
    # Event propagation means that, for example, if a layer is pressed, all its
    # child (or parent) layers receive an on_mouse_press() event as well.
    # If this kind of behavior is desired, it is the responsibility of custom
    # subclasses of Layer.


# =============================================================================

# -- TRANSITION ---------------------------------------------------------------
# Transition.update() will tween from the last value to transition.set() new
# value in the given time.
# Transitions are used as attributes (e.g. position, rotation) for the Layer
# class.

TIME = 0 # the current time in this frame changes when the canvas is updated

LINEAR = "linear"
SMOOTH = "smooth"

class Transition(object):

    def __init__(self, value, interpolation=SMOOTH):
        self._v0 = value # Previous value => Transition.start.
        self._vi = value # Current value => Transition.current.
        self._v1 = value # Desired value => Transition.stop.
        self._t0 = TIME  # Start time.
        self._t1 = TIME  # End time.
        self._interpolation = interpolation

    def copy(self):
        t = Transition(None)
        t._v0 = self._v0
        t._vi = self._vi
        t._v1 = self._v1
        t._t0 = self._t0
        t._t1 = self._t1
        t._interpolation = self._interpolation
        return t

    def get(self):
        """Return the transition stop value."""
        return self._v1

    def set(self, value, duration=1.0):
        """Set transition stop value.

        The stop value will be reached in the given duration (seconds).

        Calling Transition.update() moves the Transition.current value toward
        Transition.stop.

        """
        if not duration:
            # If no duration is given,
            # Transition.start = Transition.current = Transition.stop.
            self._vi = value

        self._v1 = value
        self._v0 = self._vi
        self._t0 = TIME # Now.
        self._t1 = TIME + duration

    @property
    def start(self):
        return self._v0

    @property
    def stop(self):
        return self._v1

    @property
    def current(self):
        return self._vi

    @property
    def done(self):
        return TIME >= self._t1

    def update(self):
        """Calculate the new current value.

        Returns True when done.

        The transition approaches the desired value according to the
        interpolation:

        - LINEAR: even transition over the given duration time,
        - SMOOTH: transition goes slower at the beginning and end.

        """
        if TIME >= self._t1 or self._vi is None:
            self._vi = self._v1
            return True
        else:
            # Calculate t: the elapsed time as a number between 0.0 and 1.0.
            t = (TIME - self._t0) / (self._t1 - self._t0)

            if self._interpolation == LINEAR:
                self._vi = self._v0 + (self._v1-self._v0) * t
            else:
                self._vi = (self._v0 + (self._v1 - self._v0) *
                            geometry.smoothstep(0.0, 1.0, t))
            return False


# -- LAYER --------------------------------------------------------------------
# The Layer class is responsible for the following:
# - it has a draw() method to override; all sorts of NodeBox drawing commands
#   can be put here,
# - it has a transformation origin point and rotates/scales its drawn items as
#   a group,
# - it has child layers that transform relative to this layer,
# - when its attributes (position, scale, angle, ...) change, they will tween
#   smoothly over time.

_UID = 0
def _uid():
    global _UID
    _UID += 1
    return _UID


RELATIVE = "relative" # Origin point is stored as float, e.g. (0.5, 0.5).
ABSOLUTE = "absolute" # Origin point is stored as int, e.g. (100, 100).


class LayerRenderError(Exception):
    pass


# When Layer.clipped=True, children are clipped to the bounds of the layer.
# The layer clipping masks lazily changes size with the layer.
class LayerClippingMask(ClippingMask):
    def __init__(self, layer):
        self.layer = layer

    def draw(self, fill=(0,0,0,1), stroke=None):
        w = not self.layer.width  and geometry.INFINITE or self.layer.width
        h = not self.layer.height and geometry.INFINITE or self.layer.height
        rect(0, 0, w, h, fill=fill, stroke=stroke)


class Layer(list, Prototype, EventHandler):

    def __init__(self, x=0, y=0, width=None, height=None, origin=(0,0),
                 scale=1.0, rotation=0, opacity=1.0, duration=0.0, name=None,
                 parent=None, **kwargs):
        """Create a new drawing layer that can be appended to the canvas.

        The duration defines the time (seconds) it takes to animate
        transformations or opacity. When the animation has terminated,
        layer.done=True.

        """
        if origin == CENTER:
            origin = (0.5, 0.5)
            origin_mode = RELATIVE
        elif isinstance(origin[0], float) and isinstance(origin[1], float):
            origin_mode = RELATIVE
        else:
            origin_mode = ABSOLUTE

        Prototype.__init__(self) # Facilitates extension on the fly.
        EventHandler.__init__(self)
        self._id = _uid()
        self.name = name                       # Layer name. Layers are accessible as ParentLayer.[name]
        self.canvas = None                     # The canvas this layer is drawn to.
        self.parent = parent                   # The layer this layer is a child of.
        self._x = Transition(x)                # Layer horizontal position in pixels, from the left.
        self._y = Transition(y)                # Layer vertical position in pixels, from the bottom.
        self._width = Transition(width)        # Layer width in pixels.
        self._height = Transition(height)      # Layer height in pixels.
        self._dx = Transition(origin[0])       # Transformation origin point.
        self._dy = Transition(origin[1])       # Transformation origin point.
        self._origin = origin_mode             # Origin point as RELATIVE or ABSOLUTE coordinates?
        self._scale = Transition(scale)        # Layer width and height scale.
        self._rotation = Transition(rotation)  # Layer rotation.
        self._opacity = Transition(opacity)    # Layer opacity.
        self.duration = duration               # The time it takes to animate transformations.
        self.top = True                        # Draw on top of or beneath parent?
        self.flipped = False                   # Flip the layer horizontally?
        self.clipped = False                   # Clip child layers to bounds?
        self.hidden = False                    # Hide the layer?
        self._transform_cache = None           # Cache of the local transformation matrix.
        self._transform_stack = None           # Cache of the cumulative transformation matrix.
        self._clipping_mask = LayerClippingMask(self)

    @classmethod
    def from_image(self, img, *args, **kwargs):
        """Return a new layer that renders the given image.

        The layer will have the same size as the image.

        The layer's draw() method and an additional image property are set.

        """
        if not isinstance(img, Image):
            img = Image(img, data=kwargs.get("data"))

        kwargs.setdefault("width", img.width)
        kwargs.setdefault("height", img.height)

        def draw(layer):
            image(layer.image)

        layer = self(*args, **kwargs)
        layer.set_method(draw)
        layer.set_property("image", img)
        return layer

    @classmethod
    def from_function(self, function, *args, **kwargs):
        """Return a new layer that renders the drawing commands in the given function.

        The layer's draw() method is set.

        """
        def draw(layer):
            function(layer)

        layer = self(*args, **kwargs)
        layer.set_method(draw)
        return layer

    def copy(self, parent=None, canvas=None):
        """Return a copy of the layer.

        All Layer properties will be copied, except for the new parent and
        canvas, which you need to define as optional parameters. This means
        that copies are not automatically appended to the parent layer or
        canvas.

        """
        # Create instance of the derived class, not Layer.
        layer = self.__class__()
        # Copy all transitions instantly.
        layer.duration = 0
        layer.canvas = canvas
        layer.parent = parent
        layer.name = self.name
        layer._x = self._x.copy()
        layer._y = self._y.copy()
        layer._width = self._width.copy()
        layer._height = self._height.copy()
        layer._origin = self._origin
        layer._dx = self._dx.copy()
        layer._dy = self._dy.copy()
        layer._scale = self._scale.copy()
        layer._rotation = self._rotation.copy()
        layer._opacity = self._opacity.copy()
        layer.duration = self.duration
        layer.top = self.top
        layer.flipped = self.flipped
        layer.clipped = self.clipped
        layer.hidden = self.hidden
        layer.enabled = self.enabled
        # Use base Layer.extend(), we don't care about what subclass.extend() does.
        Layer.extend(layer, [child.copy() for child in self])
        # Inherit all the dynamic properties and methods.
        Prototype.inherit(layer, self)
        return layer

    def __getattr__(self, key):
        """Return the given property, or the layer with the given name."""
        if key in self.__dict__:
            return self.__dict__[key]

        for layer in self:
            if layer.name == key:
                return layer

        raise AttributeError("%s instance has no attribute '%s'" %
                             (self.__class__.__name__, key))

    def _set_container(self, key, value):
        # If Layer.canvas is set to None, the canvas should no longer contain
        # the layer.
        # If Layer.canvas is set to Canvas, this canvas should contain the
        # layer.
        # Remove the layer from the old canvas/parent.
        # Append the layer to the new container.
        if self in (self.__dict__.get(key) or ()):
            self.__dict__[key].remove(self)
        if isinstance(value, list) and self not in value:
            list.append(value, self)
        self.__dict__[key] = value

    @property
    def canvas(self):
        return self.__dict__.get("canvas")

    @canvas.setter
    def canvas(self, canv):
        self._set_container("canvas", canv)

    @property
    def parent(self):
        return self.__dict__.get("parent")

    @parent.setter
    def parent(self, layer):
        self._set_container("parent", layer)

    @property
    def root(self):
        return self.parent and self.parent.root or self

    @property
    def layers(self):
        return self

    def insert(self, index, layer):
        list.insert(self, index, layer)
        layer.__dict__["parent"] = self

    def append(self, layer):
        list.append(self, layer)
        layer.__dict__["parent"] = self

    def extend(self, layers):
        for layer in layers:
            Layer.append(self, layer)

    def remove(self, layer):
        list.remove(self, layer)
        layer.__dict__["parent"] = None

    def pop(self, index):
        layer = list.pop(self, index)
        layer.__dict__["parent"] = None
        return layer

    @property
    def x(self):
        return self._x.get()

    @x.setter
    def x(self, val):
        self._transform_cache = None
        self._x.set(val, self.duration)

    @property
    def y(self):
        return self._y.get()

    @y.setter
    def y(self, val):
        self._transform_cache = None
        self._y.set(val, self.duration)

    # Do not use property decorator, because _set_width is used elsewhere
    def _get_width(self):
        return self._width.get()

    def _set_width(self, val):
        self._transform_cache = None
        self._width.set(val, self.duration)

    width = property(_get_width, _set_width)

    # Do not use property decorator, because _set_height is used elsewhere
    def _get_height(self):
        return self._height.get()

    def _set_height(self, val):
        self._transform_cache = None
        self._height.set(val, self.duration)

    height = property(_get_height, _set_height)

    @property
    def scale(self):
        return self._scale.get()

    @scale.setter
    def scale(self, val):
        self._transform_cache = None
        self._scale.set(val, self.duration)

    @property
    def rotation(self):
        return self._rotation.get()

    @rotation.setter
    def rotation(self, val):
        self._transform_cache = None
        self._rotation.set(val, self.duration)

    @property
    def opacity(self):
        return self._opacity.get()

    @opacity.setter
    def opacity(self, val):
        self._opacity.set(val, self.duration)

    @property
    def xy(self):
        return (self.x, self.y)

    @xy.setter
    def xy(self, v):
        self.x = v[0]
        self.y = v[1]

    def _get_origin(self, relative=False):
        """Returns the point from which all layer transformations originate.

        When relative=True, x and y are defined percentually (0.0-1.0) in terms
        of width and height.

        In some cases x=0 or y=0 is returned:

        - For an infinite layer (width=None or height=None), we can't deduct
          the absolute origin from coordinates stored relatively (e.g. what is
          infinity * 0.5?).

        - Vice versa, for an infinite layer we can't deduct the relative origin
          from coordinates stored absolute (e.g. what is 200/infinity?).

        """
        dx = self._dx.current
        dy = self._dy.current
        w = self._width.current
        h = self._height.current

        # Origin is stored as absolute coordinates and we want it relative.
        if self._origin == ABSOLUTE and relative:
            if w is None:
                w = 0

            if h is None:
                h = 0

            dx = dx / w if w != 0 else 0
            dy = dy / h if h != 0 else 0
        # Origin is stored as relative coordinates and we want it absolute.
        elif self._origin == RELATIVE and not relative:
            dx = w is not None and dx * w or 0
            dy = h is not None and dy * h or 0

        return dx, dy

    def _set_origin(self, x, y, relative=False):
        """Set the transformation origin point in either absolute or relative coordinates.

        For example, if a layer is 400x200 pixels, setting the origin point to
        (200,100) all transformations (translate, rotate, scale) originate from
        the center.

        """
        self._transform_cache = None
        self._dx.set(x, self.duration)
        self._dy.set(y, self.duration)
        self._origin = relative and RELATIVE or ABSOLUTE

    def origin(self, x=None, y=None, relative=False):
        """Set and return the point from which all layer transformations originate.
        """
        if x is not None:
            if x == CENTER:
                x, y, relative = 0.5, 0.5, True

            if y is not None:
                self._set_origin(x, y, relative)

        return self._get_origin(relative)

    @property
    def relative_origin(self):
        return self.origin(relative=True)

    @relative_origin.setter
    def relative_origin(self, xy):
        self._set_origin(xy[0], xy[1], relative=True)

    @property
    def absolute_origin(self):
        return self.origin(relative=False)

    @absolute_origin.setter
    def absolute_origin(self, xy):
        self._set_origin(xy[0], xy[1], relative=False)

    @property
    def visible(self):
        return not self.hidden

    @visible.setter
    def visible(self, b):
        self.hidden = not b

    def translate(self, x, y):
        self.x += x
        self.y += y

    def rotate(self, angle):
        self.rotation += angle

    def scale(self, f):
        self.scaling *= f

    def flip(self):
        self.flipped = not self.flipped

    def _update(self):
        """Called each frame by canvas._update() to update layer transitions.
        """
        done = self._x.update()
        done &= self._y.update()
        done &= self._width.update()
        done &= self._height.update()
        done &= self._dx.update()
        done &= self._dy.update()
        done &= self._scale.update()
        done &= self._rotation.update()

        if not done:  # i.e. the layer is being transformed
            self._transform_cache = None

        self._opacity.update()
        self.update()

        for layer in self:
            layer._update()

    def update(self):
        """Override this method to provide custom updating code."""
        pass

    @property
    def done(self):
        """Return True when all transitions have finished."""
        return all(
            self._x.done,
            self._y.done,
            self._width.done,
            self._height.done,
            self._dx.done,
            self._dy.done,
            self._scale.done,
            self._rotation.done,
            self._opacity.done)

    def _draw(self):
        """Draw the transformed layer and all of its children."""
        if self.hidden:
            return

        glPushMatrix()
        # Be careful that the transformations happen in the same order in
        # Layer._transform().
        # translate => flip => rotate => scale => origin.
        # Center the contents around the origin point.
        dx, dy = self.origin(relative=False)
        glTranslatef(round(self._x.current), round(self._y.current), 0)

        if self.flipped:
            glScalef(-1, 1, 1)

        glRotatef(self._rotation.current, 0, 0, 1)
        glScalef(self._scale.current, self._scale.current, 1)

        # Enable clipping mask if Layer.clipped=True.
        if self.clipped:
            beginclip(self._clipping_mask)

        # Draw child layers below.
        for layer in self:
            if layer.top is False:
                layer._draw()

        # Draw layer.
        _g.alpha = self._opacity.current  # XXX should also affect child layers?
        glPushMatrix()
        # Layers are drawn relative from parent origin.
        glTranslatef(-round(dx), -round(dy), 0)
        self.draw()
        glPopMatrix()
        _g.alpha = 1

        # Draw child layers on top.
        for layer in self:
            if layer.top is True:
                layer._draw()

        if self.clipped:
            endclip()

        glPopMatrix()

    def draw(self):
        """Override this method to provide custom drawing code for this layer.

        At this point, the layer is correctly transformed.

        """
        pass

    def render(self):
        """Return the layer as a flattened image.

        The layer and all of its children need to have width and height set.

        """
        b = self.bounds

        if geometry.INFINITE in (b.x, b.y, b.width, b.height):
            raise LayerRenderError("can't render layer of infinite size")

        return render(lambda: (translate(-b.x, -b.y), self._draw()),
                      b.width, b.height)

    def layer_at(self, x, y, clipped=False, enabled=False, transformed=True,
                 _covered=False):
        """Return the topmost layer containing the mouse position or None.

        With clipped=True, no parts of child layers outside the parent's bounds
        are checked.

        With enabled=True, only enabled layers are checked (useful for events).

        """
        if self.hidden:
            # Don't do costly operations on layers the user can't see.
            return None

        if enabled and not self.enabled:
            # Skip disabled layers during event propagation.
            return None

        if _covered:
            # An ancestor is blocking this layer, so we can't select it.
            return None

        hit = self.contains(x, y, transformed)

        if clipped:
            # If (x,y) is not inside the clipped bounds, return None.
            # If children protruding beyond the layer's bounds are clipped,
            # we only need to look at children on top of the layer.
            # Each child is drawn on top of the previous child,
            # so we hit test them in reverse order (highest-first).
            if not hit:
                return None
            children = [layer for layer in reversed(self) if layer.top is True]
        else:
            # Otherwise, traverse all children in on-top-first order to avoid
            # selecting a child underneath the layer that is in reality
            # covered by a peer on top of the layer, further down the list.
            children = sorted(reversed(self), key=lambda layer: not layer.top)
        for child in children:
            # An ancestor (e.g. grandparent) may be covering the child.
            # This happens when it hit tested and is somewhere on top of the child.
            # We keep a recursive covered-state to verify visibility.
            # The covered-state starts as False, but stays True once it switches.
            _covered = _covered or (hit and not child.top)
            child = child.layer_at(x, y, clipped, enabled, transformed, _covered)

            if child is not None:
                # Note: "if child:" won't work because it can be an empty list (no children).
                # Should be improved by not having Layer inherit from list.
                return child

        if hit:
            return self
        else:
            return None

    def _transform(self, local=True):
        """Return the transformation matrix of the layer.

        This is the calculated state of its translation, rotation and scaling.

        If local=False, prepends all transformations of the parent layers, i.e.
        you get the absolute transformation state of a nested layer.

        """
        if self._transform_cache is None:
            # Calculate the local transformation matrix.
            # Be careful that the transformations happen in the same order in
            # Layer._draw().
            # translate => flip => rotate => scale => origin.
            tf = Transform()
            dx, dy = self.origin(relative=False)
            tf.translate(round(self._x.current), round(self._y.current))

            if self.flipped:
                tf.scale(-1, 1)

            tf.rotate(self._rotation.current)
            tf.scale(self._scale.current, self._scale.current)
            tf.translate(-round(dx), -round(dy))
            self._transform_cache = tf
            # Flush the cumulative transformation cache of all children.

            def _flush(layer):
                layer._transform_stack = None

            self.traverse(_flush)
        if not local:
            # Return the cumulative transformation matrix.
            # All of the parent transformation states need to be up to date.
            # If not, we need to recalculate the whole chain.
            if self._transform_stack is None:
                if self.parent is None:
                    self._transform_stack = self._transform_cache.copy()
                else:
                    # Accumulate all the parent layer transformations.
                    # In the process, we update the transformation state of
                    # any outdated parent.
                    dx, dy = self.parent.origin(relative=False)
                    # Layers are drawn relative from parent origin.
                    tf = self.parent._transform(local=False).copy()
                    tf.translate(round(dx), round(dy))
                    self._transform_stack = self._transform_cache.copy()
                    self._transform_stack.prepend(tf)

            return self._transform_stack

        return self._transform_cache

    @property
    def transform(self):
        return self._transform(local=False)

    def _bounds(self, local=True):
        """Return the rectangle that encompasses the transformed layer and its children.

        If one of the children has width=None or height=None, bounds will be
        infinite.

        """
        w = self._width.current
        w = geometry.INFINITE if w is None else w
        h = self._height.current
        h = geometry.INFINITE if h is None else h
        # Find the transformed bounds of the layer:
        p = self.transform.map([(0, 0), (w, 0), (w, h), (0, h)])
        x = min(p[0][0], p[1][0], p[2][0], p[3][0])
        y = min(p[0][1], p[1][1], p[2][1], p[3][1])
        w = max(p[0][0], p[1][0], p[2][0], p[3][0]) - x
        h = max(p[0][1], p[1][1], p[2][1], p[3][1]) - y
        b = geometry.Bounds(x, y, w, h)

        if not local:
            for child in self:
                b = b.union(child.bounds)

        return b

    @property
    def bounds(self):
        return self._bounds(local=False)

    def contains(self, x, y, transformed=True):
        """Returns True if (x,y) falls within the layer's rectangular area.

        Useful for GUI elements: with transformed=False the calculations are
        much faster; and it will report correctly as long as the layer (or
        parent layer) is not rotated or scaled, and has its origin at (0,0).

        """
        w = self._width.current
        w = geometry.INFINITE if w is None else w
        h = self._height.current
        h = geometry.INFINITE if h is None else h

        if not transformed:
            x0, y0 = self.absolute_position()
            return x0 <= x <= x0 + w and y0 <= y <= y0 + h

        # Find the transformed bounds of the layer:
        p = self.transform.map([(0, 0), (w, 0), (w, h), (0, h)])
        return geometry.point_in_polygon(p, x, y)

    hit_test = contains

    def absolute_position(self, root=None):
        """Returns the absolute (x,y) position (i.e. cumulative with parent position).
        """
        x = 0
        y = 0
        layer = self

        while layer is not None and layer != root:
            x += layer.x
            y += layer.y
            layer = layer.parent

        return x, y

    def traverse(self, visit=lambda layer: None):
        """Recurse layer structure and calls visit() on each child layer."""
        visit(self)
        for layer in self:
            layer.traverse(visit)

    def __repr__(self):
        return ("Layer(%sx=%.2f, y=%.2f, scale=%.2f, rotation=%.2f, "
                "opacity=%.2f, duration=%.2f)" %
                ("name='%s', " % self.name if self.name else "", self.x,
                 self.y, self.scaling, self.rotation, self.opacity,
                 self.duration))

    def __eq__(self, other):
        return isinstance(other, Layer) and self._id == other._id

    def __ne__(self, other):
        return not self.__eq__(other)


layer = Layer


# -- GROUP --------------------------------------------------------------------

class Group(Layer):
    """A layer that serves as a container for other layers.

    It has no width or height and doesn't draw anything.

    """
    def __init__(self, *args, **kwargs):
        Layer.__init__(self, *args, **kwargs)
        self._set_width(0)
        self._set_height(0)

    @classmethod
    def from_image(*args, **kwargs):
        raise NotImplementedError

    @classmethod
    def from_function(*args, **kwargs):
        raise NotImplementedError

    @property
    def width(self):
        return 0

    @property
    def height(self):
        return 0

    def layer_at(self, x, y, clipped=False, enabled=False, transformed=True,
                 _covered=False):
        # Ignores clipped=True for Group (since it has no width or height).
        for child in reversed(self):
            layer = child.layer_at(x, y, clipped, enabled, transformed,
                                   _covered)

            if layer:
                return layer

group = Group


# =============================================================================

# -- MOUSE --------------------------------------------------------------------

# Mouse cursors:
DEFAULT = "default"
HIDDEN = "hidden"
CROSS = pyglet.window.Window.CURSOR_CROSSHAIR
HAND = pyglet.window.Window.CURSOR_HAND
TEXT = pyglet.window.Window.CURSOR_TEXT
WAIT = pyglet.window.Window.CURSOR_WAIT

# Mouse buttons:
LEFT = "left"
RIGHT = "right"
MIDDLE = "middle"


class Mouse(Point):
    """Keeps track of the mouse position on the canvas, buttons pressed and the cursor icon.
    """

    def __init__(self, canvas, x=0, y=0):
        Point.__init__(self, x, y)
        self._canvas = canvas
        # Mouse cursor: CROSS, HAND, HIDDEN, TEXT, WAIT.
        self._cursor = DEFAULT
        # Mouse button pressed: LEFT, RIGHT, MIDDLE.
        self._button = None
        # Mouse button modifiers: CTRL, SHIFT, OPTION.
        self.modifiers = []
        # True if the mouse button is pressed.
        self.pressed = False
        # True if the mouse is dragged.
        self.dragged = False
        # Scroll offset.
        self.scroll = Point(0, 0)
        # Relative offset from previous horizontal position.
        self.dx = 0
        # Relative offset from previous vertical position.
        self.dy = 0

    # Backwards compatibility due to an old typo:
    @property
    def vx(self):
        return self.dx

    @property
    def vy(self):
        return self.dy

    @property
    def relative_x(self):
        try:
            return float(self.x) / self._canvas.width
        except ZeroDivisionError:
            return 0

    @property
    def relative_y(self):
        try:
            return float(self.y) / self._canvas.height
        except ZeroDivisionError:
            return 0

    @property
    def cursor(self):
        return self._cursor

    @cursor.setter
    def cursor(self, mode):
        self._cursor = mode if mode != DEFAULT else None

        if mode == HIDDEN:
            self._canvas._window.set_mouse_visible(False)
            return
        self._canvas._window.set_mouse_cursor(
            self._canvas._window.get_system_mouse_cursor(
                self._cursor))

    @property
    def button(self):
        return self._button

    @button.setter
    def button(self, btn):
        self._button = (
            btn == pyglet.window.mouse.LEFT and LEFT or
            btn == pyglet.window.mouse.RIGHT and RIGHT or
            btn == pyglet.window.mouse.MIDDLE and MIDDLE or None)

    def __repr__(self):
        return "Mouse(x=%.1f, y=%.1f, pressed=%s, dragged=%s)" % (
            self.x, self.y, repr(self.pressed), repr(self.dragged))


# -- KEYBOARD -----------------------------------------------------------------

# Key codes:
BACKSPACE = "backspace"
DELETE = "delete"
TAB = "tab"
ENTER = "enter"
SPACE = "space"
ESCAPE = "escape"
UP = "up"
DOWN = "down"
LEFT = "left"
RIGHT = "right"

# Key modifiers:
OPTION = ALT = "option"
CTRL = "ctrl"
SHIFT = "shift"
COMMAND = "command"

MODIFIERS = (OPTION, CTRL, SHIFT, COMMAND)


# XXX: Use pyglet's KeyStateHandler instead
class Keys(list):
    """Keeps track of the keys pressed and any modifiers (e.g. shift or control key).
    """

    def __init__(self, canvas):
        self._canvas = canvas
        # Last key pressed
        self.code = None
        # Last key character representation (i.e., SHIFT + "a" = "A").
        self.char = ""
        # Modifier keys pressed (OPTION, CTRL, SHIFT, COMMAND).
        self.modifiers = []
        self.pressed = False

    def append(self, code):
        code = self._decode(code)
        if code in MODIFIERS:
            self.modifiers.append(code)
        list.append(self, code)
        self.code = self[-1]

    def remove(self, code):
        code = self._decode(code)
        if code in MODIFIERS:
            self.modifiers.remove(code)
        try:
            list.remove(self, code)
        except ValueError:
            # We might receive a key release without
            # having received the prior key press
            pass
        self.code = len(self) > 0 and self[-1] or None

    def _decode(self, code):
        if not isinstance(code, integer_types):
            s = code
        else:
            s = pyglet.window.key.symbol_string(code)  # 65288 => "BACKSPACE"
            s = s.lower()  # "BACKSPACE" => "backspace"
            s = s.lstrip("_")  # "_1" => "1"
            s = s.replace("return", ENTER)  # "return" => "enter"
            s = s.lstrip("num_")  # "num_space" => "space"
            # "lshift" => "shift"
            s = s.lstrip("lr") if s.endswith(MODIFIERS) else s
        return s

    def __repr__(self):
        return "Keys(char=%r, code=%r, modifiers=%r, pressed=%s)" % (
            self.char, list(self), self.modifiers, self.pressed)


# =============================================================================

# -- CANVAS -------------------------------------------------------------------

VERY_LIGHT_GREY = 0.95

FRAME = 0

# Window styles.
WINDOW_DEFAULT = pyglet.window.Window.WINDOW_STYLE_DEFAULT
WINDOW_BORDERLESS = pyglet.window.Window.WINDOW_STYLE_BORDERLESS

# Configuration settings for the canvas.
# http://www.pyglet.org/doc/programming_guide/opengl_configuration_options.html
# The stencil buffer is enabled (we need it to do clipping masks).
# Multisampling will be enabled (if possible) to do anti-aliasing.
settings = OPTIMAL = dict(
    # buffer_size = 32, # Let Pyglet decide automatically.
    # red_size = 8,
    # green_size = 8,
    # blue_size = 8,
    depth_size=24,
    stencil_size=1,
    alpha_size=8,
    double_buffer=1,
    sample_buffers=1,
    samples=4
)


def _configure(settings):
    """Return a pyglet.gl.Config object from the given dictionary of settings.

    If the settings are not supported, returns the default settings.

    """
    screen = pyglet.window.get_platform().get_default_display().get_default_screen()
    c = pyglet.gl.Config(**settings)

    try:
        c = screen.get_best_config(c)
    except pyglet.window.NoSuchConfigException:
        # Probably the hardwarde doesn't support multisampling.
        # We can still do some anti-aliasing by turning on GL_LINE_SMOOTH.
        c = pyglet.gl.Config()
        c = screen.get_best_config(c)

    return c


class Canvas(list, Prototype, EventHandler):
    """The main application window containing the drawing canvas.

    It is opened when Canvas.run() is called.

    It is a collection of drawable Layer objects, and it has its own draw()
    method. This method must be overridden with your own drawing commands,
    which will be executed each frame.

    Event handlers for keyboard and mouse interaction can also be
    overriden. Events will be passed to layers that have been appended to
    the canvas.

    """
    def __init__(self, width=640, height=480, name="NodeBox for OpenGL",
                 resizable=False, border=True, settings=OPTIMAL, vsync=True):
        window = dict(
            caption=name,
            visible=False,
            width=width,
            height=height,
            resizable=resizable,
            style=WINDOW_DEFAULT if border else WINDOW_BORDERLESS,
            config=_configure(settings),
            vsync=vsync
        )
        Prototype.__init__(self)
        EventHandler.__init__(self)
        self.profiler = Profiler(self)
        self._window = pyglet.window.Window(**window)
        self._fps = 60             # Frames per second.
        self._frame = 0            # The current frame.
        self._elapsed = 0          # dt = time elapsed since last frame.
        self._active = False       # Application is running?
        self.paused = False        # Pause animation?
        self._mouse = Mouse(self)  # The mouse cursor location.
        self._keys = Keys(self)    # The keys pressed on the keyboard.
        self._focus = None         # The layer being focused by the mouse.

        # Mouse and keyboard events:
        self._window.on_mouse_enter = self._on_mouse_enter
        self._window.on_mouse_leave = self._on_mouse_leave
        self._window.on_mouse_motion = self._on_mouse_motion
        self._window.on_mouse_press = self._on_mouse_press
        self._window.on_mouse_release = self._on_mouse_release
        self._window.on_mouse_drag = self._on_mouse_drag
        self._window.on_mouse_scroll = self._on_mouse_scroll
        self._window.on_key_pressed = False
        self._window.on_key_press = self._on_key_press
        self._window.on_key_release = self._on_key_release
        self._window.on_text = self._on_text
        self._window.on_text_motion = self._on_text_motion
        self._window.on_move = self._on_move
        self._window.on_resize = self._on_resize
        self._window.on_close = self.stop

    def insert(self, index, layer):
        list.insert(self, index, layer)
        layer.__dict__["canvas"] = self

    def append(self, layer):
        list.append(self, layer)
        layer.__dict__["canvas"] = self

    def extend(self, layers):
        for layer in layers:
            self.append(layer)

    def remove(self, layer):
        list.remove(self, layer)
        layer.__dict__["canvas"] = None

    def pop(self, index):
        layer = list.pop(index)
        layer.__dict__["canvas"] = None
        return layer

    @property
    def name(self):
        return self._window.caption

    @name.setter
    def name(self, s):
        self._window.set_caption(s)

    @property
    def vsync(self):
        return self._window.vsync

    @vsync.setter
    def vsync(self, bool):
        self._window.set_vsync(bool)

    @property
    def layers(self):
        return self

    @property
    def x(self):
        return self._window.get_location()[0]

    @x.setter
    def x(self, v):
        self._window.set_location(v, self.y)

    @property
    def y(self):
        return self._window.get_location()[1]

    @y.setter
    def y(self, v):
        self._window.set_location(self.x, v)

    @property
    def xy(self):
        return (self.x, self.y)

    @xy.setter
    def xy(self, v):
        self.x = v[0]
        self.y = v[1]

    @property
    def width(self):
        return self._window.width

    @width.setter
    def width(self, v):
        self._window.width = v

    @property
    def height(self):
        return self._window.height

    @height.setter
    def height(self, v):
        self._window.height = v

    @property
    def size(self):
        return (self.width, self.height)

    @size.setter
    def size(self, wh):
        self.width = wh[0]
        self.height = wh[1]

    @property
    def fullscreen(self):
        return self._window.fullscreen

    @fullscreen.setter
    def fullscreen(self, mode=True):
        self._window.set_fullscreen(mode)

    @property
    def screen(self):
        return pyglet.window.get_platform().get_default_display().get_default_screen()

    @property
    def frame(self):
        """Yield the current frame number (1-based)."""
        return self._frame

    @property
    def elapsed(self):
        """Yield the elapsed time since last frame."""
        return self._elapsed

    dt = elapsed

    @property
    def mouse(self):
        """Yield a Point(x, y) with the mouse position on the canvas."""
        return self._mouse

    @property
    def keys(self):
        return self._keys

    @property  # Backwards compatibility.
    def key(self):
        return self._keys

    @property
    def focus(self):
        return self._focus

    # -- Event dispatchers ----------------------------------------------------
    # First events are dispatched, then update() and draw() are called.

    def layer_at(self, x, y, **kwargs):
        """Find the topmost layer at the specified coordinates.

        This method returns None if no layer was found.

        """
        for layer in reversed(self):
            layer = layer.layer_at(x, y, **kwargs)
            if layer is not None:
                return layer
        return None

    def _on_mouse_enter(self, x, y):
        self._mouse.x = x
        self._mouse.y = y
        self.on_mouse_enter(self._mouse)

    def _on_mouse_leave(self, x, y):
        self._mouse.x = x
        self._mouse.y = y
        self.on_mouse_leave(self._mouse)

        # When the mouse leaves the canvas, no layer has the focus.
        # Quirk: Ignore on_mouse_leave events generated by xlib
        # when the mouse is pressed inside the layer with the focus
        layer = self.layer_at(x, y, enabled=True)
        if self._focus is not None and self._focus != layer:
            self._focus.on_mouse_leave(self._mouse)
            self._focus.focus = False
            self._focus.pressed = False
            self._focus.dragged = False
            self._focus = None

    def _on_mouse_motion(self, x, y, dx, dy):
        self._mouse.x = x
        self._mouse.y = y
        self._mouse.dx = int(dx)
        self._mouse.dy = int(dy)
        self.on_mouse_motion(self._mouse)
        # Get the topmost layer over which the mouse is hovering.
        layer = self.layer_at(x, y, enabled=True)

        # If the layer differs from the layer which currently has the focus,
        # or the mouse is not over any layer, remove the current focus.
        if (self._focus is not None and
                (self._focus != layer or not self._focus.contains(x, y))):
            self._focus.on_mouse_leave(self._mouse)
            self._focus.focus = False
            self._focus = None

        # Set the focus.
        if self.focus != layer and layer is not None:
            self._focus = layer
            self._focus.focus = True
            self._focus.on_mouse_enter(self._mouse)

        # Propagate mouse motion to layer with the focus.
        if self._focus is not None:
            self._focus.on_mouse_motion(self._mouse)

    def _on_mouse_press(self, x, y, button, modifiers):
        self._mouse.pressed = True
        self._mouse.button = button
        self._mouse.modifiers = [a for (a, b) in (
            (CTRL, pyglet.window.key.MOD_CTRL),
            (SHIFT, pyglet.window.key.MOD_SHIFT),
            (OPTION, pyglet.window.key.MOD_OPTION)) if modifiers & b]
        self.on_mouse_press(self._mouse)

        # Propagate mouse clicking to the layer with the focus.
        if self._focus is not None:
            self._focus.pressed = True
            self._focus.on_mouse_press(self._mouse)

    def _on_mouse_release(self, x, y, button, modifiers):
        if self._focus is not None:
            self._focus.on_mouse_release(self._mouse)
            self._focus.pressed = False
            self._focus.dragged = False

        self.on_mouse_release(self._mouse)
        self._mouse.button = None
        self._mouse.modifiers = []
        self._mouse.pressed = False
        self._mouse.dragged = False

        if self._focus is not None:
            # Get the topmost layer over which the mouse is hovering.
            layer = self.layer_at(x, y, enabled=True)

            # If the mouse is no longer over the layer with the focus
            # (this can happen after dragging), remove the focus.
            if self._focus != layer or not self._focus.contains(x, y):
                self._focus.on_mouse_leave(self._mouse)
                self._focus.focus = False
                self._focus = None

            # Propagate mouse to the layer with the focus.
            if self._focus != layer and layer is not None:
                layer.focus = True
                layer.on_mouse_enter(self._mouse)

            self._focus = layer

    def _on_mouse_drag(self, x, y, dx, dy, buttons, modifiers):
        self._mouse.dragged = True
        self._mouse.x = x
        self._mouse.y = y
        self._mouse.dx = int(dx)
        self._mouse.dy = int(dy)
        self._mouse.modifiers = [a for (a, b) in (
            (CTRL, pyglet.window.key.MOD_CTRL),
            (SHIFT, pyglet.window.key.MOD_SHIFT),
            (OPTION, pyglet.window.key.MOD_OPTION)) if modifiers & b]
        # XXX also needs to log buttons.
        self.on_mouse_drag(self._mouse)

        # Propagate mouse dragging to the layer with the focus.
        if self._focus is not None:
            self._focus.dragged = True
            self._focus.on_mouse_drag(self._mouse)

    def _on_mouse_scroll(self, x, y, scroll_x, scroll_y):
        self._mouse.scroll.x = scroll_x
        self._mouse.scroll.y = scroll_y
        self.on_mouse_scroll(self._mouse)

        # Propagate mouse scrolling to the layer with the focus.
        if self._focus is not None:
            self._focus.on_mouse_scroll(self._mouse)

    def _on_key_press(self, keycode, modifiers):
        self._keys.pressed = True
        self._keys.append(keycode)

        if self._keys.code == TAB:
            self._keys.char = "\t"

        # The event is delegated in _update():
        self._window.on_key_pressed = True

    def _on_key_release(self, keycode, modifiers):
        for layer in self:
            layer.on_key_release(self.key)

        self.on_key_release(self.key)
        self._keys.char = ""
        self._keys.remove(keycode)
        self._keys.pressed = False

    def _on_text(self, text):
        self._keys.char = text
        # The event is delegated in _update():
        self._window.on_key_pressed = True

    def _on_text_motion(self, keycode):
        self._keys.char = ""
        # The event is delegated in _update():
        self._window.on_key_pressed = True

    def _on_move(self, x, y):
        self.on_move()

    def _on_resize(self, width, height):
        pyglet.window.Window.on_resize(self._window, width, height)
        self.on_resize()

    # Event methods are meant to be overridden
    # or patched with Prototype.set_method().
    def on_key_press(self, keys):
        """The default behavior of the canvas:

        - ESC exits the application,
        - CTRL-P pauses the animation,
        - CTRL-S saves a screenshot.

        """
        if keys.code == ESCAPE:
            self.stop()

        if keys.code == "p" and CTRL in keys.modifiers:
            self.paused = not self.paused

        if keys.code == 'f11':
            self.fullscreen = not self.fullscreen

        if keys.code == "s" and CTRL in keys.modifiers:
            now = datetime.now()
            self.save("nodebox-%s.png" % now.strftime('%Y-%m-%d-%H-%M-%S'))

    def on_move(self):
        pass

    def on_resize(self):
        pass

    # -- Main loop ------------------------------------------------------------

    def setup(self):
        pass

    def update(self):
        pass

    def draw(self):
        self.clear()

    def draw_overlay(self):
        """Override this method to draw once all the layers have been drawn."""
        pass

    draw_over = draw_overlay

    def _setup(self):
        """Initialize the application window and resets the state.

        Clears the canvas and calls Canvas.setup().

        """
        # Start the application (if not already running).
        if not self._active:
            self._window.switch_to()
            # Set the window color, this will be transparent in saved images.
            glClearColor(VERY_LIGHT_GREY, VERY_LIGHT_GREY, VERY_LIGHT_GREY, 0)
            # Reset the transformation state.
            # Most of this is already taken care of in Pyglet.
            #glMatrixMode(GL_PROJECTION)
            #glLoadIdentity()
            #glOrtho(0, self.width, 0, self.height, -1, 1)
            #glMatrixMode(GL_MODELVIEW)
            glLoadIdentity()
            # Enable line anti-aliasing.
            glEnable(GL_LINE_SMOOTH)
            # Enable alpha transparency.
            glEnable(GL_BLEND)
            glBlendFuncSeparate(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA, GL_ONE,
                                GL_ONE_MINUS_SRC_ALPHA)
            #glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
            self._window.dispatch_events()
            self._window.set_visible(True)
            self._active = True

        self.clear()
        self.setup()

    def _draw(self, lapse=0):
        """Draw the canvas and its layers.

        This method gives the same result each time it gets drawn; only
        _update() advances state.

        """
        if self.paused:
            return

        self._window.switch_to()
        glPushMatrix()
        self.draw()
        glPopMatrix()
        glPushMatrix()

        for layer in self:
            layer._draw()

        glPopMatrix()
        glPushMatrix()
        self.draw_overlay()
        glPopMatrix()

    def _update(self, lapse=0):
        """Update the canvas and its layers.

        This method does not actually draw anything, it only updates the state.

        """
        self._elapsed = lapse

        if not self.paused:
            # Advance the animation by updating all layers.
            # This is only done when the canvas is not paused.
            # Events will still be propagated during pause.
            global TIME
            TIME = time()
            self._frame += 1
            self.update()

            for layer in self:
                layer._update()

        if self._window.on_key_pressed is True:
            # Fire on_key_press() event,
            # which combines _on_key_press(), _on_text() and _on_text_motion().
            self._window.on_key_pressed = False
            self.on_key_press(self._keys)

            for layer in self:
                layer.on_key_press(self._keys)

    def stop(self):
        # If you override this method, don't forget to call Canvas.stop() to
        # exit the app.
        # Any user-defined stop method, added with canvas.set_method() or
        # canvas.run(stop=stop), is called first.
        try:
            self._user_defined_stop()
        except:
            pass

        for f in (self._update, self._draw):
            pyglet.clock.unschedule(f)

        self._window.close()
        self._active = False
        pyglet.app.exit()

    def clear(self):
        """Clear the previous frame from the canvas."""
        glClear(GL_COLOR_BUFFER_BIT)
        glClear(GL_DEPTH_BUFFER_BIT)
        glClear(GL_STENCIL_BUFFER_BIT)

    def run(self, draw=None, setup=None, update=None, stop=None):
        """Open the application windows and start drawing the canvas.

        - Canvas.setup() will be called once during initialization.
        - Canvas.draw() and Canvas.update() will be called each frame.
        - Canvas.clear() needs to be called explicitly to clear the previous
          frame drawing.
        - Canvas.stop() closes the application window.

        If the given setup, draw or update parameter is a function, it
        overrides that canvas method.

        """
        if isinstance(setup, FunctionType):
            self.set_method(setup, name="setup")

        if isinstance(draw, FunctionType):
            self.set_method(draw, name="draw")

        if isinstance(update, FunctionType):
            self.set_method(update, name="update")

        if isinstance(stop, FunctionType):
            self.set_method(stop, name="stop")

        self._setup()
        self.fps = self._fps  # Schedule the _update and _draw events.
        pyglet.app.run()

    @property
    def active(self):
        return self._active

    @property
    def fps(self):
        return self._fps

    @fps.setter
    def fps(self, v):
        # Use pyglet.clock to schedule _update() and _draw() events.
        # The clock will then take care of calling them enough times.
        # Note: frames per second is related to vsync.
        # If the vertical refresh rate is about 30Hz you'll get top speed of
        # around 33fps.
        # It's probably a good idea to leave vsync=True if you don't want to
        # fry the GPU.
        for f in (self._update, self._draw):
            pyglet.clock.unschedule(f)

            if v is None:
                pyglet.clock.schedule(f)

            if v > 0:
                pyglet.clock.schedule_interval(f, 1.0 / v)

        self._fps = v

    # -- Frame export ---------------------------------------------------------

    def render(self):
        """Returns a screenshot of the current frame as a texture.

        This texture can be passed to the image() command.

        """
        return pyglet.image.get_buffer_manager().get_color_buffer().get_texture()

    buffer = screenshot = render

    @property
    def texture(self):
        return pyglet.image.get_buffer_manager().get_color_buffer().get_texture()

    def save(self, path):
        """Export the current frame as a PNG-file."""
        pyglet.image.get_buffer_manager().get_color_buffer().save(path)

    # -- Prototype ------------------------------------------------------------

    def __setattr__(self, k, v):
        # Canvas is a Prototype, so Canvas.draw() can be overridden
        # but it can also be patched with Canvas.set_method(draw).
        # Specific methods (setup, draw, mouse and keyboard events) can also be
        # set directly (e.g. canvas.on_mouse_press = my_mouse_handler).
        # This way we don't have to explain set_method() to beginning users..
        handlers = (
            "on_mouse_enter",
            "on_mouse_leave",
            "on_mouse_motion",
            "on_mouse_press",
            "on_mouse_release",
            "on_mouse_drag",
            "on_mouse_scroll",
            "on_key_press",
            "on_key_release",
            "on_move",
            "on_resize"
        )
        api = ("setup", "draw", "update", "stop")
        if (isinstance(v, FunctionType)
                and (k in api or k.startswith("on_") and k in handlers)):
            self.set_method(v, name=k)
        else:
            object.__setattr__(self, k, v)

    def set_method(self, function, name=None):
        if (name == "stop" or name is None and function.__name__ == "stop"):
            # Called from Canvas.stop().
            Prototype.set_method(self, function, name="_user_defined_stop")
        else:
            Prototype.set_method(self, function, name)

    def __repr__(self):
        return "Canvas(name='%s', size='%s', layers=%s)" % (
            self.name, self.size, repr(list(self)))


# -- PROFILER -----------------------------------------------------------------


CUMULATIVE = "cumulative"
SLOWEST = "slowest"

_profile_canvas = None
_profile_frames = 100


def profile_run():
    for i in range(_profile_frames):
        _profile_canvas._update()
        _profile_canvas._draw()


class Profiler(object):
    """Executes a number of frames of animation under a the Python profiler.

    Returns a string with performance statistics

    """
    def __init__(self, canvas):
        self.canvas = canvas

    @property
    def framerate(self):
        return pyglet.clock.get_fps()

    def run(self, draw=None, setup=None, update=None, frames=100,
            sort=CUMULATIVE, top=30):
        """Runs cProfile on the canvas for the given number of frames.

        The performance statistics are returned as a string, sorted by SLOWEST
        or CUMULATIVE.

        For example, instead of doing canvas.run(draw):

            print canvas.profiler.run(draw, frames=100)

        """
        # Register setup, draw, update functions with the canvas (if given).
        if isinstance(setup, FunctionType):
            self.canvas.set_method(setup, name="setup")

        if isinstance(draw, FunctionType):
            self.canvas.set_method(draw, name="draw")

        if isinstance(update, FunctionType):
            self.canvas.set_method(update, name="update")

        # Set the current canvas and the number of frames to profile.
        # The profiler will then repeatedly execute canvas._update() and
        # canvas._draw().
        # Statistics are redirected from stdout to a temporary file.
        global _profile_canvas, _profile_frames
        _profile_canvas = self.canvas
        _profile_frames = frames
        import cProfile
        import pstats
        cProfile.run("profile_run()", "_profile")
        p = pstats.Stats("_profile")
        p.stream = open("_profile", "w")
        p.sort_stats("time" if sort == SLOWEST else sort).print_stats(top)
        p.stream.close()
        s = open("_profile").read()
        remove("_profile")
        return s


# -- LIBRARIES ----------------------------------------------------------------
def ximport(library):
    """Import the library and assign it a _ctx variable containing the
    current context.

    This mimics the behavior in NodeBox for Mac OS X.

    """
    from sys import modules
    library = __import__(library)
    library._ctx = modules[__name__]
    return library
