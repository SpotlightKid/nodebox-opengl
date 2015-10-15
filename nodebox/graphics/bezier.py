# -*- coding: utf-8 -*-
# == BEZIER ===================================================================
# Bezier mathematics.
# Authors: Tom De Smedt
# License: BSD (see LICENSE.txt for details).
# Copyright (c) 2008-2012 City In A Bottle (cityinabottle.org)
# http://cityinabottle.org/nodebox

# Thanks to Prof. F. De Smedt at the Vrije Universiteit Brussel.
"""A BezierPath class with lineto(), curveto() and moveto() commands.

It has all the path math functionality from NodeBox and a ray casting algorithm
for contains().

A number of caching mechanisms are used for performance: drawn vertices,
segment lengths, path bounds, and a hit test area for BezierPath.contains().
For optimal performance, the path should be created once (not every frame) and
left unmodified.

When points in the path are added, removed or modified, a _dirty flag is set.
When dirty, the cache will be cleared and the new path recalculated.

If the path is being drawn with a fill color, this means doing tessellation
(i.e. additional math for finding out if parts overlap and punch a hole in the
shape).

The module also contains functions for linear interpolation math for
BezierPath.point() etc.

"""


from __future__ import absolute_import

from math import acos, ceil, sin, cos, hypot, pow, sqrt, radians, degrees

from pyglet.gl import *

from . import geometry as geo
from .caching import flush, precompile
from .glext import glLineDash
from .state import global_state as _g, state_mixin


__all__ = (
    'MOVETO',
    'LINETO',
    'CURVETO',
    'CLOSE',
    'RELATIVE_PRECISION',
    'BezierEditor',
    'BezierPath',
    'ClippingMask',
    'DynamicPathElement',
    'NoCurrentPath',
    'NoCurrentPointForPath',
    'Path',
    'PathElement',
    'PathError',
    'PathPoint',
    'arc',
    'arcto',
    'autoclosepath',
    'beginclip',
    'beginpath',
    'closepath',
    'contours',
    'curvepoint',
    'curveto',
    'directed',
    'drawpath',
    'endclip',
    'endpath',
    'findpath',
    'insert_point',
    'length',
    'linelength',
    'lineto',
    'moveto',
    'pointonpath',
    'pointsonpath',
    'segment_lengths'
)


# PathElement point format
MOVETO = "moveto"
LINETO = "lineto"
CURVETO = "curveto"
CLOSE = "close"


# Number of straight lines to represent a curve = 20% of curve length.
RELATIVE_PRECISION = 0.2

# BezierEditor
EQUIDISTANT = "equidistant"
# Drag pt1.ctrl2, pt2.ctrl1 or both simultaneously?
IN = "in"
OUT = "out"
BOTH = "both"


class PathError(Exception):
    pass


class NoCurrentPointForPath(Exception):
    pass


class NoCurrentPath(Exception):
    pass


def drawpath(path, **kwargs):
    """Draw the given BezierPath (or list of PathElements).

    The current stroke, strokewidth and fill color are applied.

    """
    if not isinstance(path, BezierPath):
        path = BezierPath(path)
    path.draw(**kwargs)


def autoclosepath(close=False):
    """Paths constructed with beginpath() and endpath() are automatically closed.
    """
    _g.autoclosepath = close


def beginpath(x, y):
    """Start a new path at (x,y).

    The commands moveto(), lineto(), curveto() and closepath() can then be used
    between beginpath() and endpath() calls.

    """
    _g.path = BezierPath()
    _g.path.moveto(x, y)


def moveto(x, y):
    """Move the current point in the current path to (x,y)."""
    if _g.path is None:
        raise NoCurrentPath

    _g.path.moveto(x, y)


def lineto(x, y):
    """Draw a line from the current point in the current path to (x,y)."""
    if _g.path is None:
        raise NoCurrentPath

    _g.path.lineto(x, y)


def curveto(x1, y1, x2, y2, x3, y3):
    """Draw a curve from the current point in the current path to (x3, y3).

    The curvature is determined by control handles x1, y1 and x2, y2.

    """
    if _g.path is None:
        raise NoCurrentPath

    _g.path.curveto(x1, y1, x2, y2, x3, y3)


def closepath():
    """Close the current path with a straight line to the last MOVETO."""
    if _g.path is None:
        raise NoCurrentPath

    _g.path.closepath()


def endpath(draw=True, **kwargs):
    """Draw and return the current path.

    With draw=False, only returns the path so it can be manipulated and drawn
    with drawpath().

    """

    if _g.path is None:
        raise NoCurrentPath

    if _g.autoclosepath is True:
        _g.path.closepath()

    if draw:
        _g.path.draw(**kwargs)

    p, _g.path = _g.path, None
    return p


class PathPoint(geo.Point):
    """A control handle for PathElement."""

    def __init__(self, x=0, y=0):
        self._x = x
        self._y = y
        self._dirty = False

    @property
    def x(self):
        return self._x

    @x.setter
    def x(self, v):
        self._x = v
        self._dirty = True

    @property
    def y(self):
        return self._y

    @y.setter
    def y(self, v):
        self._y = v
        self._dirty = True

    def copy(self, parent=None):
        return PathPoint(self._x, self._y)


class PathElement(object):
    """A point in the path, optionally with control handles."""

    def __init__(self, cmd=None, pts=None):
        """Create path element with given command and points.

        The format of the given points depend on the command:

        - MOVETO  : the list of points contains a single (x,y)-tuple.
        - LINETO  : the list of points contains a single (x,y)-tuple.
        - CURVETO : the list of points contains (vx1, vy1), (vx2, vy2),
                    (x, y) tuples.
        - CLOSETO : no points.

        """
        if cmd == MOVETO or cmd == LINETO:
            pt, h1, h2 = pts[0], pts[0], pts[0]
        elif cmd == CURVETO:
            pt, h1, h2 = pts[2], pts[0], pts[1]
        else:
            pt, h1, h2 = (0, 0), (0, 0), (0, 0)

        self._cmd = cmd
        self._x = pt[0]
        self._y = pt[1]
        self._ctrl1 = PathPoint(h1[0], h1[1])
        self._ctrl2 = PathPoint(h2[0], h2[1])
        self.__dirty = False

    @property
    def dirty(self):
        return self.__dirty \
            or self.ctrl1._dirty \
            or self.ctrl2._dirty

    @dirty.setter
    def dirty(self, b):
        self.__dirty = b
        self.ctrl1._dirty = b
        self.ctrl2._dirty = b

    @property
    def cmd(self):
        return self._cmd

    @property
    def x(self):
        return self._x

    @x.setter
    def x(self, v):
        self._x = v
        self.__dirty = True

    @property
    def y(self):
        return self._y

    @y.setter
    def y(self, v):
        self._y = v
        self.__dirty = True

    @property
    def xy(self):
        return (self.x, self.y)

    @xy.setter
    def xy(self, v):
        self.x = v[0]
        self.y = v[1]

    # Handle 1 describes now the curve from the previous point started.
    @property
    def ctrl1(self):
        return self._ctrl1

    @ctrl1.setter
    def ctrl1(self, v):
        self._ctrl1 = PathPoint(v.x, v.y)
        self.__dirty = True

    # Handle 2 describes how the curve from the previous point
    # arrives in this point.
    @property
    def ctrl2(self):
        return self._ctrl2

    @ctrl2.setter
    def ctrl2(self, v):
        self._ctrl2 = PathPoint(v.x, v.y)
        self.__dirty = True

    def __eq__(self, pt):
        if not isinstance(pt, PathElement):
            return False

        return (self.cmd == pt.cmd
                and self.x == pt.x
                and self.y == pt.y
                and self.ctrl1 == pt.ctrl1
                and self.ctrl2 == pt.ctrl2)

    def __ne__(self, pt):
        return not self.__eq__(pt)

    def __repr__(self):
        return "%s(cmd='%s', x=%.1f, y=%.1f, ctrl1=(%.1f, %.1f), ctrl2=(%.1f, %.1f))" % (
            self.__class__.__name__, self.cmd, self.x, self.y,
            self.ctrl1.x, self.ctrl1.y,
            self.ctrl2.x, self.ctrl2.y)

    def copy(self):
        if self.cmd == MOVETO or self.cmd == LINETO:
            pts = ((self.x, self.y),)
        elif self.cmd == CURVETO:
            pts = ((self.ctrl1.x, self.ctrl1.y), (self.ctrl2.x, self.ctrl2.y),
                   (self.x, self.y))
        else:
            pts = None

        return PathElement(self.cmd, pts)


class DynamicPathElement(PathElement):
    """Not a "fixed" point in the BezierPath,

    But calculated with BezierPath.point().

    """
    pass


class BezierPath(list):
    """A list of PathElements describing the curves and lines making up a path.
    """

    def __init__(self, path=None, **kwargs):
        if isinstance(path, (BezierPath, list, tuple)):
            self.extend([pt.copy() for pt in path])

        self._kwargs = kwargs
        self._cache = None     # Cached vertices for drawing.
        self._segments = None  # Cached segment lengths.
        self._bounds = None    # Cached bounding rectangle.
        self._polygon = None   # Cached polygon hit test area.
        self._dirty = False
        self._index = {}

    def copy(self):
        return BezierPath(self, **self._kwargs)

    def append(self, pt):
        self._dirty = True
        list.append(self, pt)

    def extend(self, points):
        self._dirty = True
        list.extend(self, points)

    def insert(self, i, pt):
        self._dirty = True
        self._index={}
        list.insert(self, i, pt)

    def remove(self, pt):
        self._dirty = True
        self._index={}
        list.remove(self, pt)

    def pop(self, i):
        self._dirty = True
        self._index={}
        list.pop(self, i)

    def __setitem__(self, i, pt):
        self._dirty = True
        self._index={}
        list.__setitem__(self, i, pt)

    def __delitem__(self, i):
        self._dirty = True
        self._index={}
        list.__delitem__(self, i)

    def sort(self):
        self._dirty = True
        self._index={}
        list.sort(self)

    def reverse(self):
        self._dirty = True
        self._index={}
        list.reverse(self)

    def index(self, pt):
        return self._index.setdefault(pt, list.index(self, pt))

    def _update(self):
        # Called from BezierPath.draw().
        # If points were added or removed, clear the cache.
        b = self._dirty
        for pt in self:
            b = b or pt._dirty
            pt._dirty = False

        if b:
            if self._cache is not None:
                if self._cache[0]: flush(self._cache[0])
                if self._cache[1]: flush(self._cache[1])

            self._cache = self._segments = self._bounds = self._polygon = None
            self._dirty = False

    def moveto(self, x, y):
        """Add a new point to the path at x, y."""
        self.append(PathElement(MOVETO, ((x, y),)))

    def lineto(self, x, y):
        """Add a line from the previous point to x, y."""
        self.append(PathElement(LINETO, ((x, y),)))

    def curveto(self, x1, y1, x2, y2, x3, y3):
        """Add a Bezier-curve from the previous point to x3, y3.

        The curvature is determined by control handles x1, y1 and x2, y2.

        """
        self.append(PathElement(CURVETO, ((x1, y1), (x2, y2), (x3, y3))))

    def arcto(self, x, y, radius=1, clockwise=True, short=False):
        """Add a number of Bezier-curves that draw an arc with the given radius to (x,y).

        The short parameter selects either the "long way" around or the
        "shortcut".

        """
        x0, y0 = self[-1].x, self[-1].y
        phi = geo.angle(x0, y0, x, y)

        for p in arcto(x0, y0, radius, radius, phi, short, not clockwise, x, y):
            f = len(p) == 2 and self.lineto or self.curveto
            f(*p)

    def closepath(self):
        """Add a line from the previous point to the last MOVETO."""
        self.append(PathElement(CLOSE))

    def rect(self, x, y, width, height, roundness=0.0):
        """Adds a (rounded) rectangle to the path.

        Corner roundness can be given as a relative float or absolute int.

        """
        if roundness <= 0:
            self.moveto(x, y)
            self.lineto(x + width, y)
            self.lineto(x + width, y + height)
            self.lineto(x, y + height)
            self.lineto(x, y)
        else:
            if isinstance(roundness, int):
                r = min(roundness, width / 2, height / 2)
            else:
                r = min(width, height)
                r = min(roundness, 1) * r * 0.5

            self.moveto(x + r, y)
            self.lineto(x + width - r, y)
            self.arcto(x + width, y + r, radius=r, clockwise=False)
            self.lineto(x + width, y + height - r)
            self.arcto(x + width - r, y + height, radius=r, clockwise=False)
            self.lineto(x + r, y + height)
            self.arcto(x, y + height - r, radius=r, clockwise=False)
            self.lineto(x, y + r)
            self.arcto(x + r, y, radius=r, clockwise=False)

    def ellipse(self, x, y, width, height):
        """Add an ellipse to the path."""

        w, h = width*0.5, height*0.5
        k = 0.5522847498    # kappa: (-1 + sqrt(2)) / 3 * 4
        self.moveto(x, y-h) # http://www.whizkidtech.redprince.net/bezier/circle/
        self.curveto(x+w*k, y-h,   x+w,   y-h*k, x+w, y, )
        self.curveto(x+w,   y+h*k, x+w*k, y+h,   x,   y+h)
        self.curveto(x-w*k, y+h,   x-w,   y+h*k, x-w, y, )
        self.curveto(x-w,   y-h*k, x-w*k, y-h,   x,   y-h)
        self.closepath()

    oval = ellipse

    def arc(self, x, y, width, height, start=0, stop=90):
        """Adds an arc to the path.

        The arc follows the ellipse defined by (x, y, width, height), with
        start and stop specifying what angle range to draw.

        """
        w, h = width * 0.5, height * 0.5

        for i, p in enumerate(arc(x-w, y-h, x+w, y+h, start, stop)):
            if i == 0:
                self.moveto(*p[:2])

            self.curveto(*p[2:])

    def smooth(self, *args, **kwargs):
        """Smooths the path by making the curve handles colinear.

        With mode=EQUIDISTANT, the curve handles will be of equal (average)
        length.

        """
        e = BezierEditor(self)

        for i, pt in enumerate(self):
            self._index[pt] = i
            e.smooth(pt, *args, **kwargs)

    def flatten(self, precision=RELATIVE_PRECISION):
        """Return a list of contours, where each is a list of (x,y)-tuples.

        The precision determines the number of straight lines to use as a
        substition for a curve. It can be a fixed number (int) or relative to
        the curve length (float or RELATIVE_PRECISION).

        """
        contours = [[]]
        x0 = y0 = None
        closeto = None

        for pt in self:
            if pt.cmd in (LINETO, CURVETO) and x0 is None and y0 is None:
                raise NoCurrentPointForPath
            elif pt.cmd == LINETO:
                contours[-1].append((x0, y0))
                contours[-1].append((pt.x, pt.y))
            elif pt.cmd == CURVETO:
                # Curves are interpolated from a number of straight line
                # segments.
                # With relative precision, we use the (rough) curve length to
                # determine the number of lines.
                x1, y1, x2 = pt.ctrl1.x, pt.ctrl1.y, pt.ctrl2.x
                y2, x3, y3 = pt.ctrl2.y, pt.x, pt.y

                if isinstance(precision, float):
                    n = int(max(0, precision) * curvelength(
                        x0, y0, x1, y1, x2, y2, x3, y3, 3))
                else:
                    n = int(max(0, precision))

                if n > 0:
                    xi, yi = x0, y0

                    for i in range(n+1):
                        xj, yj, vx1, vy1, vx2, vy2 = curvepoint(
                            float(i)/n, x0, y0, x1, y1, x2, y2, x3, y3)
                        contours[-1].append((xi, yi))
                        contours[-1].append((xj, yj))
                        xi, yi = xj, yj
            elif pt.cmd == MOVETO:
                contours.append([]) # Start a new contour.
                closeto = pt
            elif pt.cmd == CLOSE and closeto is not None:
                contours[-1].append((x0, y0))
                contours[-1].append((closeto.x, closeto.y))

            x0, y0 = pt.x, pt.y

        return contours

    def draw(self, precision=RELATIVE_PRECISION, **kwargs):
        """Draw the path.

        The precision determines the number of straight lines to use as a
        substition for a curve. It can be a fixed number (int) or relative to
        the curve length (float or RELATIVE_PRECISION).

        """
        if len(kwargs) > 0:
            # Optional parameters in draw() overrule those set during
            # initialization.
            kw = dict(self._kwargs)
            kw.update(kwargs)
            fill, stroke, strokewidth, strokestyle = state_mixin(**kw)
        else:
            fill, stroke, strokewidth, strokestyle = state_mixin(**self._kwargs)

        def _draw_fill(contours):
            # Drawing commands for the path fill
            # (as triangles by tessellating the contours).
            v = geo.tesselate(contours)
            glBegin(GL_TRIANGLES)

            for x, y in v:
                glVertex3f(x, y, 0)

            glEnd()

        def _draw_stroke(contours):
            # Drawing commands for the path stroke.
            for path in contours:
                glBegin(GL_LINE_STRIP)

                for x, y in path:
                    glVertex2f(x, y)

                glEnd()

        self._update() # Remove the cache if points were modified.

        if (self._cache is None or
                self._cache[0] is None and fill or
                self._cache[1] is None and stroke or
                self._cache[-1] != precision):
            # Calculate and cache the vertices as Display Lists.
            # If the path requires a fill color, it will have to be tessellated.
            if self._cache is not None:
                if self._cache[0]:
                    flush(self._cache[0])
                if self._cache[1]:
                    flush(self._cache[1])

            contours = self.flatten(precision)
            self._cache = [None, None, precision]

            if fill:
                self._cache[0] = precompile(_draw_fill, contours)
            if stroke:
                self._cache[1] = precompile(_draw_stroke, contours)

        if fill is not None:
            glColor4f(fill[0], fill[1], fill[2], fill[3] * _g.alpha)
            glCallList(self._cache[0])

        if stroke is not None and strokewidth > 0:
            glColor4f(stroke[0], stroke[1], stroke[2], stroke[3] * _g.alpha)
            glLineWidth(strokewidth)
            glLineDash(strokestyle)
            glCallList(self._cache[1])

    def angle(self, t):
        """Return the directional angle at time t (0.0-1.0) on the path."""
        # The directed() enumerator is much faster but less precise.
        pt0, pt1 = (self.point(t), self.point(t+0.001)) if t == 0 else (self.point(t-0.001), self.point(t))
        return geo.angle(pt0.x, pt0.y, pt1.x, pt1.y)

    def point(self, t):
        """Return the PathElement at time t (0.0-1.0) on the path.

        See the linear interpolation math in the function in the section BEZIER
        MATH in this module.

        """
        if self._segments is None:
            self._segments = length(self, segmented=True, n=10)

        return pointonpath(self, t, segments=self._segments)

    def points(self, amount=2, start=0.0, end=1.0):
        """Return a list of PathElements along the path.

        To omit the last point on closed paths: end=1-1.0/amount

        """
        if self._segments is None:
            self._segments = length(self, segmented=True, n=10)

        return pointsonpath(self, amount, start, end, segments=self._segments)

    def addpoint(self, t):
        """Inserts a new PathElement at time t (0.0-1.0) on the path."""
        self._segments = None
        self._index = {}
        return insert_point(self, t)

    split = addpoint

    @property
    def length(self, precision=10):
        """Return an approximation of the total length of the path."""
        return length(self, segmented=False, n=precision)

    @property
    def contours(self):
        """Return a list of contours (i.e. segments separated by a MOVETO) in the path.

        Each contour is a BezierPath object.

        """
        return contours(self)

    @property
    def bounds(self, precision=100):
        """Return a (x, y, w, h)-tuple of the approximate path dimensions."""
        # In _update(), traverse all the points and check if they have changed.
        # If so, the bounds must be recalculated.
        self._update()

        if self._bounds is None:
            l = t = float( "inf")
            r = b = float("-inf")

            for pt in self.points(precision):
                if pt.x < l: l = pt.x
                if pt.y < t: t = pt.y
                if pt.x > r: r = pt.x
                if pt.y > b: b = pt.y

            self._bounds = (l, t, r-l, b-t)

        return self._bounds

    def contains(self, x, y, precision=100):
        """Return True if point (x,y) falls within the contours of the path."""
        bx, by, bw, bh = self.bounds
        if bx <= x <= bx+bw and by <= y <= by+bh:
            if self._polygon is None or self._polygon[1] != precision:
                self._polygon = [(pt.x,pt.y) for pt in self.points(precision)], precision
            # Ray casting algorithm:
            return geo.point_in_polygon(self._polygon[0], x, y)

        return False

    def hash(self, state=None, decimal=1):
        """Return the path id, based on the position and handles of its PathElements.

        Two distinct BezierPath objects that draw the same path therefore have
        the same id.

        """
        # Format floats as strings with given decimal precision.
        f = lambda x: int(x * 10 ** decimal)
        id = [state]

        for pt in self:
            id.extend((
            pt.cmd, f(pt.x), f(pt.y), f(pt.ctrl1.x), f(pt.ctrl1.y), f(pt.ctrl2.x), f(pt.ctrl2.y)))

        id = str(id)
        id = md5(id).hexdigest()
        return id

    def __repr__(self):
        return "BezierPath(%s)" % repr(list(self))

    def __del__(self):
        # Note: it is important that __del__() is called since it unloads the cache from GPU.
        # BezierPath and PathElement should contain no circular references, e.g. no PathElement.parent.
        if hasattr(self, "_cache") and self._cache is not None and flush:
            if self._cache[0]: flush(self._cache[0])
            if self._cache[1]: flush(self._cache[1])


Path = BezierPath


#==============================================================================

#--- BEZIER MATH --------------------------------------------------------------

try:
    # Fast C implementations:
    from nodebox.ext.bezier import linepoint, linelength, curvepoint, curvelength
except ImportError:
    def linepoint(t, x0, y0, x1, y1):
        """Returns coordinates for point at t on the line.

        Calculates the coordinates of x and y for a point at t on a straight
        line.

        The t parameter is a number between 0.0 and 1.0,
        x0 and y0 define the starting point of the line,
        x1 and y1 the ending point of the line.

        """
        out_x = x0 + t * (x1-x0)
        out_y = y0 + t * (y1-y0)
        return (out_x, out_y)


    def linelength(x0, y0, x1, y1):
        """Returns the length of the line.
        """
        a = pow(abs(x0 - x1), 2)
        b = pow(abs(y0 - y1), 2)
        return sqrt(a+b)


    def curvepoint(t, x0, y0, x1, y1, x2, y2, x3, y3, handles=False):
        """Returns coordinates for point at t on the spline.

        Calculates the coordinates of x and y for a point at t on the cubic
        bezier spline, and its control points, based on the de Casteljau
        interpolation algorithm.

        The t parameter is a number between 0.0 and 1.0,
        x0 and y0 define the starting point of the spline,
        x1 and y1 its control point,
        x3 and y3 the ending point of the spline,
        x2 and y2 its control point.

        If the handles parameter is set, returns not only the point at t, but
        the modified control points of p0 and p3 should this point split the
        path as well.

        """
        mint = 1 - t
        x01 = x0 * mint + x1 * t
        y01 = y0 * mint + y1 * t
        x12 = x1 * mint + x2 * t
        y12 = y1 * mint + y2 * t
        x23 = x2 * mint + x3 * t
        y23 = y2 * mint + y3 * t
        out_c1x = x01 * mint + x12 * t
        out_c1y = y01 * mint + y12 * t
        out_c2x = x12 * mint + x23 * t
        out_c2y = y12 * mint + y23 * t
        out_x = out_c1x * mint + out_c2x * t
        out_y = out_c1y * mint + out_c2y * t

        if not handles:
            return (out_x, out_y, out_c1x, out_c1y, out_c2x, out_c2y)
        else:
            return (out_x, out_y, out_c1x, out_c1y, out_c2x, out_c2y, x01, y01, x23, y23)


    def curvelength(x0, y0, x1, y1, x2, y2, x3, y3, n=20):
        """Returns the length of the spline.

        Integrates the estimated length of the cubic bezier spline defined by
        x0, y0, ... x3, y3, by adding the lengths of linear lines between
        points at t.

        The number of points is defined by n (n=10 would add the lengths of
        lines between 0.0 and 0.1, between 0.1 and 0.2, and so on). The default
        n=20 is fine for most cases, usually resulting in a deviation of less
        than 0.01.

        """
        length = 0
        xi = x0
        yi = y0

        for i in range(n):
            t = 1.0 * (i+1) / n
            pt_x, pt_y, pt_c1x, pt_c1y, pt_c2x, pt_c2y = \
                curvepoint(t, x0, y0, x1, y1, x2, y2, x3, y3)
            c = sqrt(pow(abs(xi-pt_x),2) + pow(abs(yi-pt_y),2))
            length += c
            xi = pt_x
            yi = pt_y

        return length


#--- BEZIER PATH LENGTH -------------------------------------------------------

def segment_lengths(path, relative=False, n=20):
    """Returns a list with the lengths of each segment in the path."""
    lengths = []
    first = True
    for el in path:
        if first == True:
            close_x, close_y = el.x, el.y
            first = False
        elif el.cmd == MOVETO:
            close_x, close_y = el.x, el.y
            lengths.append(0.0)
        elif el.cmd == CLOSE:
            lengths.append(linelength(x0, y0, close_x, close_y))
        elif el.cmd == LINETO:
            lengths.append(linelength(x0, y0, el.x, el.y))
        elif el.cmd == CURVETO:
            x3, y3, x1, y1, x2, y2 = el.x, el.y, el.ctrl1.x, el.ctrl1.y, el.ctrl2.x, el.ctrl2.y
            lengths.append(curvelength(x0, y0, x1, y1, x2, y2, x3, y3, n))

        if el.cmd != CLOSE:
            x0 = el.x
            y0 = el.y

    if relative:
        length = sum(lengths)

        try:
            # Relative segment lengths' sum is 1.0.
            return map(lambda l: l / length, lengths)
        except ZeroDivisionError:
            # If the length is zero, just return zero for all segments
            return [0.0] * len(lengths)
    else:
        return lengths


def length(path, segmented=False, n=20):
    """Returns the length of the path.

    Calculates the length of each spline in the path, using n as a number of
    points to measure. When segmented is True, returns a list containing the
    individual length of each spline as values between 0.0 and 1.0, defining
    the relative length of each spline in relation to the total path length.

    """
    if not segmented:
        return sum(segment_lengths(path, n=n), 0.0)
    else:
        return segment_lengths(path, relative=True, n=n)


#--- BEZIER PATH POINT --------------------------------------------------------

def _locate(path, t, segments=None):
    """Locates t on a specific segment in the path.

    Returns (index, t, PathElement)

    A path is a combination of lines and curves (segments).

    The returned index indicates the start of the segment that contains point t.

    The returned t is the absolute time on that segment, in contrast to the
    relative t on the whole of the path.

    The returned point is the last MOVETO, any subsequent CLOSETO after i
    closes to that point. When you supply the list of segment lengths yourself,
    as returned from length(path, segmented=True), pointonpath() works about
    thirty times faster in a for-loop since it doesn't need to recalculate the
    length during each iteration.

    """
    if segments == None:
        segments = segment_lengths(path, relative=True)

    if len(segments) == 0:
        raise PathError("The given path is empty")

    for i, el in enumerate(path):
        if i == 0 or el.cmd == MOVETO:
            closeto = geo.Point(el.x, el.y)

        if t <= segments[i] or i == len(segments)-1:
            break
        else:
            t -= segments[i]

    try:
        t /= segments[i]
    except ZeroDivisionError:
        pass

    if i == len(segments)-1 and segments[i] == 0:
        i -= 1

    return (i, t, closeto)


def pointonpath(path, t, segments=None):
    """Returns coordinates for point at t on the path.

    Gets the length of the path, based on the length of each curve and line in
    the path.

    Determines in what segment t falls. Gets the point on that segment.

    When you supply the list of segment lengths yourself, as returned from
    length(path, segmented=True), pointonpath() works about thirty times faster
    in a for-loop since it doesn't need to recalculate the length during each
    iteration.

    """
    if len(path) == 0:
        raise PathError("The given path is empty")

    i, t, closeto = _locate(path, t, segments=segments)
    x0, y0 = path[i].x, path[i].y
    p1 = path[i+1]

    if p1.cmd == CLOSE:
        x, y = linepoint(t, x0, y0, closeto.x, closeto.y)
        return DynamicPathElement(LINETO, ((x, y),))
    elif p1.cmd == LINETO:
        x1, y1 = p1.x, p1.y
        x, y = linepoint(t, x0, y0, x1, y1)
        return DynamicPathElement(LINETO, ((x, y),))
    elif p1.cmd == CURVETO:
        # Note: the handles need to be interpreted differenty than in a BezierPath.
        # In a BezierPath, ctrl1 is how the curve started, and ctrl2 how it arrives in this point.
        # Here, ctrl1 is how the curve arrives, and ctrl2 how it continues to the next point.
        x3, y3, x1, y1, x2, y2 = p1.x, p1.y, p1.ctrl1.x, p1.ctrl1.y, p1.ctrl2.x, p1.ctrl2.y
        x, y, c1x, c1y, c2x, c2y = curvepoint(t, x0, y0, x1, y1, x2, y2, x3, y3)
        return DynamicPathElement(CURVETO, ((c1x, c1y), (c2x, c2y), (x, y)))
    else:
        raise PathError("Unknown cmd '%s' for p1 %s" % (p1.cmd, p1))


def pointsonpath(path, amount=100, start=0.0, end=1.0, segments=None):
    """Returns an iterator with a list of calculated points for the path.

    To omit the last point on closed paths: end=1 - 1.0 / amount

    """
    if len(path) == 0:
        raise PathError("The given path is empty")

    n = end - start
    d = n

    if amount > 1:
        # The delta value is divided by amount-1, because we also want the last point (t=1.0)
        # If we don't use amount-1, we fall one point short of the end.
        # If amount=4, we want the point at t 0.0, 0.33, 0.66 and 1.0.
        # If amount=2, we want the point at t 0.0 and 1.0.
        d = float(n) / (amount-1)

    for i in xrange(amount):
        yield pointonpath(path, start + d * i, segments)


#--- BEZIER PATH CONTOURS -----------------------------------------------------

def contours(path):
    """Returns a list of contours in the path, as BezierPath objects.

    A contour is a sequence of lines and curves separated from the next contour
    by a MOVETO. For example, the glyph "o" has two contours: the inner circle
    and the outer circle.

    """
    contours = []
    current_contour = None
    empty = True
    for i, el in enumerate(path):
        if el.cmd == MOVETO:
            if not empty:
                contours.append(current_contour)
            current_contour = BezierPath()
            current_contour.moveto(el.x, el.y)
            empty = True
        elif el.cmd == LINETO:
            empty = False
            current_contour.lineto(el.x, el.y)
        elif el.cmd == CURVETO:
            empty = False
            current_contour.curveto(el.ctrl1.x, el.ctrl1.y, el.ctrl2.x, el.ctrl2.y, el.x, el.y)
        elif el.cmd == CLOSE:
            current_contour.closepath()
    if not empty:
        contours.append(current_contour)
    return contours


#--- BEZIER PATH FROM POINTS --------------------------------------------------

def findpath(points, curvature=1.0):
    """Constructs a smooth BezierPath from the given list of points.

    The curvature parameter offers some control on how separate segments are
    stitched together: from straight angles to smooth curves. Curvature is only
    useful if the path has more than three points.

    """
    # The list of points consists of geometry.Point objects,
    # but it shouldn't crash on something straightforward
    # as someone supplying a list of (x,y)-tuples.

    for i, pt in enumerate(points):
        if isinstance(pt, tuple):
            points[i] = geo.Point(pt[0], pt[1])

    # No points: return nothing.
    if len(points) == 0: return None

    # One point: return a path with a single MOVETO-point.
    if len(points) == 1:
        path = BezierPath(None)
        path.moveto(points[0].x, points[0].y)
        return path

    # Two points: path with a single straight line.
    if len(points) == 2:
        path = BezierPath(None)
        path.moveto(points[0].x, points[0].y)
        path.lineto(points[1].x, points[1].y)
        return path

    # Zero curvature means path with straight lines.
    curvature = max(0, min(1, curvature))

    if curvature == 0:
        path = BezierPath(None)
        path.moveto(points[0].x, points[0].y)

        for i in range(len(points)):
            path.lineto(points[i].x, points[i].y)

        return path

    # Construct the path with curves.
    curvature = 4 + (1.0-curvature)*40

    # The first point's ctrl1 and ctrl2 and last point's ctrl2
    # will be the same as that point's location;
    # we cannot infer how the path curvature started or will continue.
    dx = {0: 0, len(points)-1: 0}
    dy = {0: 0, len(points)-1: 0}
    bi = {1: -0.25}
    ax = {1: (points[2].x-points[0].x-dx[0]) / 4}
    ay = {1: (points[2].y-points[0].y-dy[0]) / 4}

    for i in range(2, len(points)-1):
        bi[i] = -1 / (curvature + bi[i-1])
        ax[i] = -(points[i+1].x-points[i-1].x-ax[i-1]) * bi[i]
        ay[i] = -(points[i+1].y-points[i-1].y-ay[i-1]) * bi[i]

    r = range(1, len(points)-1)
    r.reverse()

    for i in r:
        dx[i] = ax[i] + dx[i+1] * bi[i]
        dy[i] = ay[i] + dy[i+1] * bi[i]

    path = BezierPath(None)
    path.moveto(points[0].x, points[0].y)

    for i in range(len(points)-1):
        path.curveto(points[i].x + dx[i],
                     points[i].y + dy[i],
                     points[i+1].x - dx[i+1],
                     points[i+1].y - dy[i+1],
                     points[i+1].x,
                     points[i+1].y)

    return path


# -- BEZIER PATH INSERT POINT -------------------------------------------------

def insert_point(path, t):
    """Inserts an extra point at t."""

    # Find the points before and after t on the path.
    i, t, closeto = _locate(path, t)
    x0 = path[i].x
    y0 = path[i].y
    p1 = path[i+1]
    p1cmd, x3, y3, x1, y1, x2, y2 = p1.cmd, p1.x, p1.y, p1.ctrl1.x, p1.ctrl1.y, p1.ctrl2.x, p1.ctrl2.y

    # Construct the new point at t.
    if p1cmd == CLOSE:
        pt_cmd = LINETO
        pt_x, pt_y = linepoint(t, x0, y0, closeto.x, closeto.y)
    elif p1cmd == LINETO:
        pt_cmd = LINETO
        pt_x, pt_y = linepoint(t, x0, y0, x3, y3)
    elif p1cmd == CURVETO:
        pt_cmd = CURVETO
        pt_x, pt_y, pt_c1x, pt_c1y, pt_c2x, pt_c2y, pt_h1x, pt_h1y, pt_h2x, pt_h2y = \
            curvepoint(t, x0, y0, x1, y1, x2, y2, x3, y3, True)
    else:
        raise PathError("Locate should not return a MOVETO")

    # NodeBox for OpenGL modifies the path in place,
    # NodeBox for Mac OS X returned a path copy (see inactive code below).
    if pt_cmd == CURVETO:
        path[i+1].ctrl1.x = pt_c2x
        path[i+1].ctrl1.y = pt_c2y
        path[i+1].ctrl2.x = pt_h2x
        path[i+1].ctrl2.y = pt_h2y
        path.insert(i + 1, PathElement(cmd=CURVETO, pts=[(pt_h1x, pt_h1y), (pt_c1x, pt_c1y), (pt_x, pt_y)]))
    elif pt_cmd == LINETO:
        path.insert(i + 1, PathElement(cmd=LINETO, pts=[(pt_x, pt_y)]))
    else:
        raise PathError("Didn't expect pt_cmd %s here" % pt_cmd)

    return path[i + 1]

    #new_path = BezierPath(None)
    #new_path.moveto(path[0].x, path[0].y)
    #for j in range(1, len(path)):
    #    if j == i+1:
    #        if pt_cmd == CURVETO:
    #            new_path.curveto(pt_h1x, pt_h1y, pt_c1x, pt_c1y, pt_x, pt_y)
    #            new_path.curveto(pt_c2x, pt_c2y, pt_h2x, pt_h2y, path[j].x, path[j].y)
    #        elif pt_cmd == LINETO:
    #            new_path.lineto(pt_x, pt_y)
    #            if path[j].cmd != CLOSE:
    #                new_path.lineto(path[j].x, path[j].y)
    #            else:
    #                new_path.closepath()
    #        else:
    #            raise PathError("Didn't expect pt_cmd %s here" % pt_cmd)
    #    else:
    #        if path[j].cmd == MOVETO:
    #            new_path.moveto(path[j].x, path[j].y)
    #        if path[j].cmd == LINETO:
    #            new_path.lineto(path[j].x, path[j].y)
    #        if path[j].cmd == CURVETO:
    #            new_path.curveto(path[j].ctrl1.x, path[j].ctrl1.y,
    #                         path[j].ctrl2.x, path[j].ctrl2.y,
    #                         path[j].x, path[j].y)
    #        if path[j].cmd == CLOSE:
    #            new_path.closepath()

    return new_path


# =============================================================================

# -- BEZIER ARC ---------------------------------------------------------------

# Copyright (c) 2005-2008, Enthought, Inc.
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# Redistributions of source code must retain the above copyright notice,
# this list of conditions and the following disclaimer.
# Redistributions in binary form must reproduce the above copyright notice,
# this list of conditions and the following disclaimer in the documentation
# and/or other materials provided with the distribution.
# Neither the name of Enthought, Inc. nor the names of its contributors
# may be used to endorse or promote products derived from this software
# without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO,
# THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR
# PURPOSE ARE DISCLAIMED.
# IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE LIABLE FOR ANY
# DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
# (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
# LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND
# ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
# SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

def arc(x1, y1, x2, y2, angle=0, extent=90):
    """Compute a cubic Bezier approximation of an elliptical arc.

    (x1, y1) and (x2, y2) are the corners of the enclosing rectangle.

    The coordinate system has coordinates that increase to the right and down.
    Angles, measured in degrees, start with 0 to the right (the positive X
    axis) and increase counter-clockwise.

    The arc extends from angle to angle+extent. I.e. angle=0 and extent=180
    yields an openside-down semi-circle.

    The resulting coordinates are of the form (x1,y1, x2,y2, x3,y3, x4,y4) such
    that the curve goes from (x1, y1) to (x4, y4) with (x2, y2) and (x3, y3) as
    their respective Bezier control points.

    """
    x1, y1, x2, y2 = min(x1, x2), max(y1, y2), max(x1, x2), min(y1, y2)
    extent = min(max(extent, -360), 360)
    n = abs(extent) <= 90 and 1 or int(ceil(abs(extent) / 90.0))
    a = float(extent) / n
    cx = float(x1 + x2) / 2
    cy = float(y1 + y2) / 2
    rx = float(x2 - x1) / 2
    ry = float(y2 - y1) / 2
    a2 = radians(a) / 2
    kappa = abs(4.0 / 3 * (1 - cos(a2)) / sin(a2))
    points = []
    for i in range(n):
        theta0 = radians(angle + (i + 0) * a)
        theta1 = radians(angle + (i + 1) * a)
        c0, c1 = cos(theta0), cos(theta1)
        s0, s1 = sin(theta0), sin(theta1)
        k = a > 0 and -kappa or kappa
        points.append((
            cx + rx * c0,
            cy - ry * s0,
            cx + rx * (c0 + k * s0),
            cy - ry * (s0 - k * c0),
            cx + rx * (c1 - k * s1),
            cy - ry * (s1 + k * c1),
            cx + rx * c1,
            cy - ry * s1
        ))
    return points


def arcto(x1, y1, rx, ry, phi, large_arc, sweep, x2, y2):
    """An elliptical arc approximated with Bezier curves or a line segment.

    Algorithm taken from the SVG 1.1 Implementation Notes:
    http://www.w3.org/TR/SVG/implnote.html#ArcImplementationNotes

    """
    def angle(x1, y1, x2, y2):
        a = degrees(acos(min(max((x1 * x2 + y1 * y2) / hypot(x1, y1) *
                                 hypot(x2, y2), -1), 1)))
        return x1 * y2 > y1 * x2 and a or -a

    def abspt(x, y, cphi, sphi, mx, my):
        return (x * cp - y * sp + mx,
                x * sp + y * cp + my)

    if x1 == x2 and y1 == y2:
        return []

    if rx == 0 or ry == 0:  # Line segment.
        return [(x2, y2)]

    rx, ry, phi = abs(rx), abs(ry), phi % 360
    cp = cos(radians(phi))
    sp = sin(radians(phi))

    # Rotate to the local coordinates.
    dx = 0.5 * (x1 - x2)
    dy = 0.5 * (y1 - y2)
    x = cp * dx + sp * dy
    y = -sp * dx + cp * dy

    # If rx, ry and phi are such that there is no solution (basically, the
    # ellipse is not big enough to reach from (x1, y1) to (x2, y2)) then the
    # ellipse is scaled up uniformly until there is exactly one solution
    # (until the ellipse is just big enough).
    s = (x / rx) ** 2 + (y / ry) ** 2
    if s > 1.0:
        s = sqrt(s)
        rx, ry = rx * s, ry * s

    # Solve for the center in the local coordinates.
    a = sqrt(max((rx * ry) ** 2 - (rx * y) ** 2 - (ry * x) ** 2, 0) /
             ((rx * y) ** 2 + (ry * x) ** 2))
    a = large_arc == sweep and -a or a
    cx = a * rx * y / ry
    cy = -a * ry * x / rx

    # Transform back.
    mx = 0.5 * (x1 + x2)
    my = 0.5 * (y1 + y2)

    # Compute the start angle and the angular extent of the arc.
    # Note that theta is local to the phi-rotated coordinate space.
    dx1 = (x - cx) / rx
    dy1 = (y - cy) / ry
    dx2 = (-x - cx) / rx
    dy2 = (-y - cy) / ry
    theta = angle(1.0, 0.0, dx1, dy1)
    delta = angle(dx1, dy1, dx2, dy2)

    if not sweep and delta > 0:
        delta -= 360

    if sweep and delta < 0:
        delta += 360

    # Break it apart into Bezier curves.
    points = []
    handles = arc(cx - rx, cy - ry, cx + rx, cy + ry, theta, delta)

    for x1, y1, x2, y2, x3, y3, x4, y4 in handles:
        points.append((
            abspt(x2, y2, cp, sp, mx, my) +
            abspt(x3, y3, cp, sp, mx, my) +
            abspt(x4, y4, cp, sp, mx, my)
        ))

    return points


# -- BEZIER EDITOR ------------------------------------------------------------

class BezierEditor(object):

    def __init__(self, path):
        self.path = path

    def _nextpoint(self, pt):
        i = self.path.index(pt)  # BezierPath caches this operation.
        return i < len(self.path) - 1 and self.path[i + 1] or None

    def translate(self, pt, x=0, y=0, h1=(0, 0), h2=(0, 0)):
        """Translate the point and its control handles by (x,y).

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
        """Rotate the point control handles by the given angle."""
        pt1, pt2 = pt, self._nextpoint(pt)

        if handle in (BOTH, IN):
            pt1.ctrl2.x, pt1.ctrl2.y = geo.rotate(pt1.ctrl2.x,
                pt1.ctrl2.y, pt1.x, pt1.y, angle)

        if handle in (BOTH, OUT) and pt2 is not None and pt2.cmd == CURVETO:
            pt2.ctrl1.x, pt2.ctrl1.y = geo.rotate(pt2.ctrl1.x,
                pt2.ctrl1.y, pt1.x, pt1.y, angle)

    def scale(self, pt, v, handle=BOTH):
        """Scale the point control handles by the given factor."""
        pt1, pt2 = pt, self._nextpoint(pt)

        if handle in (BOTH, IN):
            pt1.ctrl2.x, pt1.ctrl2.y = linepoint(v, pt1.x, pt1.y, pt1.ctrl2.x,
                                                 pt1.ctrl2.y)

        if handle in (BOTH, OUT) and pt2 is not None and pt2.cmd == CURVETO:
            pt2.ctrl1.x, pt2.ctrl1.y = linepoint(v, pt1.x, pt1.y, pt2.ctrl1.x,
                                                 pt2.ctrl1.y)

    def smooth(self, pt, mode=None, handle=BOTH):
        pt1, pt2, i = pt, self._nextpoint(pt), self.path.index(pt)

        if pt2 is None:
            return

        if pt1.cmd == pt2.cmd == CURVETO:
            if mode == EQUIDISTANT:
                d1 = d2 = 0.5 * (
                    geo.distance(pt1.x, pt1.y, pt1.ctrl2.x, pt1.ctrl2.y) +
                    geo.distance(pt1.x, pt1.y, pt2.ctrl1.x, pt2.ctrl1.y))
            else:
                d1 = geo.distance(pt1.x, pt1.y, pt1.ctrl2.x, pt1.ctrl2.y)
                d2 = geo.distance(pt1.x, pt1.y, pt2.ctrl1.x, pt2.ctrl1.y)

            if handle == IN:
                a = geo.angle(pt1.x, pt1.y, pt1.ctrl2.x, pt1.ctrl2.y)
            elif handle == OUT:
                a = geo.angle(pt2.ctrl1.x, pt2.ctrl1.y, pt1.x, pt1.y)
            elif handle == BOTH:
                a = geo.angle(pt2.ctrl1.x, pt2.ctrl1.y, pt1.ctrl2.x, pt1.ctrl2.y)

            pt1.ctrl2.x, pt1.ctrl2.y = geo.coordinates(pt1.x, pt1.y, d1, a)
            pt2.ctrl1.x, pt2.ctrl1.y = geo.coordinates(pt1.x, pt1.y, d2, a - 180)
        elif pt1.cmd == CURVETO and pt2.cmd == LINETO:
            d = mode == (geo.distance(pt1.x, pt1.y, pt2.x, pt2.y)
                if EQUIDISTANT else
                geo.distance(pt1.x, pt1.y, pt1.ctrl2.x, pt1.ctrl2.y))
            a = geo.angle(pt1.x, pt1.y, pt2.x, pt2.y)
            pt1.ctrl2.x, pt1.ctrl2.y = geo.coordinates(pt1.x, pt1.y, d, a - 180)
        elif pt1.cmd == LINETO and pt2.cmd == CURVETO and i > 0:
            d = mode == (geo.distance(pt1.x, pt1.y, self.path[i - 1].x,
                                      self.path[i - 1].y)
                         if EQUIDISTANT else
                         geo.distance(pt1.x, pt1.y, pt2.ctrl1.x, pt2.ctrl1.y))
            a = geo.angle(self.path[i - 1].x, self.path[i - 1].y, pt1.x, pt1.y)
            pt2.ctrl1.x, pt2.ctrl1.y = geo.coordinates(pt1.x, pt1.y, d, a)


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
        if 0 < i < n - 1 and pt.__dict__.get("_cmd") == CURVETO:
            # For a point on a curve, the control handle gives the best
            # direction.
            # For PathElement (fixed point in BezierPath), ctrl2 tells us how
            # the curve arrives.
            # For DynamicPathElement (returnd from BezierPath.point()), ctrl1
            # tells how the curve arrives.
            ctrl = isinstance(pt, DynamicPathElement) and pt.ctrl1 or pt.ctrl2
            angle = geo.angle(ctrl.x, ctrl.y, pt.x, pt.y)
        elif (0 < i < n - 1 and pt.__dict__.get("_cmd") == LINETO
                and p[i - 1].__dict__.get("_cmd") == CURVETO):
            # For a point on a line preceded by a curve, look ahead gives
            # better results.
            angle = geo.angle(pt.x, pt.y, p[i + 1].x, p[i + 1].y)
        elif i == 0 and isinstance(points, BezierPath):
            # For the first point in a BezierPath, we can calculate a next
            # point very close by.
            pt1 = points.point(0.001)
            angle = geo.angle(pt.x, pt.y, pt1.x, pt1.y)
        elif i == n - 1 and isinstance(points, BezierPath):
            # For the last point in a BezierPath, we can calculate a previous
            # point very close by.
            pt0 = points.point(0.999)
            angle = geo.angle(pt0.x, pt0.y, pt.x, pt.y)
        elif (i == n - 1 and isinstance(pt, DynamicPathElement)
                and pt.ctrl1.x != pt.x or pt.ctrl1.y != pt.y):
            # For the last point in BezierPath.points(), use incoming handle
            # (ctrl1) for curves.
            angle = geo.angle(pt.ctrl1.x, pt.ctrl1.y, pt.x, pt.y)
        elif 0 < i:
            # For any point, look back gives a good result, if enough points
            # are given.
            angle = geo.angle(p[i - 1].x, p[i - 1].y, pt.x, pt.y)
        elif i < n - 1:
            # For the first point, the best (only) guess is the location of the
            # next point.
            angle = geo.angle(pt.x, pt.y, p[i + 1].x, p[i + 1].y)
        else:
            angle = 0

        yield angle, pt


# -- CLIPPING PATH ------------------------------------------------------------

class ClippingMask(object):
    def draw(self, fill=(0, 0, 0, 1), stroke=None):
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
    # Disregard color settings; always use a black mask.
    path.draw(fill=(0, 0, 0, 1), stroke=None)
    #glEnable(GL_DEPTH_TEST)
    glStencilFunc(GL_EQUAL, 1, 1)
    glStencilOp(GL_KEEP, GL_KEEP, GL_KEEP)


def endclip():
    glDisable(GL_STENCIL_TEST)
