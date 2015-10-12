# -*- coding: utf-8 -*-
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

"""

from __future__ import absolute_import, print_function

__all__ = (
    'BezierPath',
    'NoCurrentPath',
    'NoCurrentPointForPath',
    'Path',
    'PathError',
    'PathPoint',
    'MOVETO',
    'LINETO',
    'CURVETO',
    'CLOSE',
    'RELATIVE',
    'RELATIVE_PRECISION'
)

from .geometry import Point


MOVETO  = "moveto"
LINETO  = "lineto"
CURVETO = "curveto"
CLOSE   = "close"

RELATIVE = "relative"
# Number of straight lines to represent a curve = 20% of curve length.
RELATIVE_PRECISION = 0.2


class PathError(Exception):
    pass


class NoCurrentPointForPath(Exception):
    pass


class NoCurrentPath(Exception):
    pass


class PathPoint(Point):
    """A control handle for PathElement."""

    def __init__(self, x=0, y=0):
        self._x = x
        self._y = y
        self._dirty = False

    def _get_x(self): return self._x
    def _set_x(self, v):
        self._x = v
        self._dirty = True

    def _get_y(self): return self._y
    def _set_y(self, v):
        self._y = v
        self._dirty = True

    x = property(_get_x, _set_x)
    y = property(_get_y, _set_y)

    def copy(self, parent=None):
        return PathPoint(self._x, self._y)


class PathElement(object):
    """A point in the path, optionally with control handles."""

    def __init__(self, cmd=None, pts=None):
        """Create path element with given command and points.

        The format of the given points depend on the command:

        - MOVETO  : the list of points contains a single (x,y)-tuple.
        - LINETO  : the list of points contains a single (x,y)-tuple.
        - CURVETO : the list of points contains (vx1,vy1), (vx2,vy2), (x,y) tuples.
        - CLOSETO : no points.

        """
        if cmd == MOVETO or cmd == LINETO:
            pt, h1, h2 = pts[0], pts[0], pts[0]
        elif cmd == CURVETO:
            pt, h1, h2 = pts[2], pts[0], pts[1]
        else:
            pt, h1, h2 = (0,0), (0,0), (0,0)

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
    def xy(self, (x,y)):
        self.x = x
        self.y = y

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
        phi = geometry.angle(x0, y0, x, y)

        for p in bezier.arcto(x0, y0, radius, radius, phi, short, not clockwise, x, y):
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

        for i, p in enumerate(bezier.arc(x-w, y-h, x+w, y+h, start, stop)):
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

    def flatten(self, precision=RELATIVE):
        """Return a list of contours, in which each contour is a list of (x,y)-tuples.

        The precision determines the number of straight lines to use as a
        substition for a curve. It can be a fixed number (int) or relative to
        the curve length (float or RELATIVE).

        """
        if precision == RELATIVE:
            precision = RELATIVE_PRECISION

        contours = [[]]
        x0, y0 = None, None
        closeto = None

        for pt in self:
            if (pt.cmd == LINETO or pt.cmd == CURVETO) and x0 == y0 is None:
                raise NoCurrentPointForPath
            elif pt.cmd == LINETO:
                contours[-1].append((x0, y0))
                contours[-1].append((pt.x, pt.y))
            elif pt.cmd == CURVETO:
                # Curves are interpolated from a number of straight line segments.
                # With relative precision, we use the (rough) curve length to determine the number of lines.
                x1, y1, x2, y2, x3, y3 = pt.ctrl1.x, pt.ctrl1.y, pt.ctrl2.x, pt.ctrl2.y, pt.x, pt.y

                if isinstance(precision, float):
                    n = int(max(0, precision) * bezier.curvelength(x0, y0, x1, y1, x2, y2, x3, y3, 3))
                else:
                    n = int(max(0, precision))

                if n > 0:
                    xi, yi = x0, y0

                    for i in range(n+1):
                        xj, yj, vx1, vy1, vx2, vy2 = bezier.curvepoint(float(i)/n, x0, y0, x1, y1, x2, y2, x3, y3)
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

    def draw(self, precision=RELATIVE, **kwargs):
        """Draw the path.

        The precision determines the number of straight lines to use as a
        substition for a curve. It can be a fixed number (int) or relative to
        the curve length (float or RELATIVE).

        """
        if len(kwargs) > 0:
            # Optional parameters in draw() overrule those set during initialization.
            kw = dict(self._kwargs)
            kw.update(kwargs)
            fill, stroke, strokewidth, strokestyle = color_mixin(**kw)
        else:
            fill, stroke, strokewidth, strokestyle = color_mixin(**self._kwargs)

        def _draw_fill(contours):
            # Drawing commands for the path fill
            # (as triangles by tessellating the contours).
            v = geometry.tesselate(contours)
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
            glColor4f(fill[0], fill[1], fill[2], fill[3] * _alpha)
            glCallList(self._cache[0])

        if stroke is not None and strokewidth > 0:
            glColor4f(stroke[0], stroke[1], stroke[2], stroke[3] * _alpha)
            glLineWidth(strokewidth)
            glLineDash(strokestyle)
            glCallList(self._cache[1])

    def angle(self, t):
        """Return the directional angle at time t (0.0-1.0) on the path."""
        # The directed() enumerator is much faster but less precise.
        pt0, pt1 = (self.point(t), self.point(t+0.001)) if t == 0 else (self.point(t-0.001), self.point(t))
        return geometry.angle(pt0.x, pt0.y, pt1.x, pt1.y)

    def point(self, t):
        """Return the PathElement at time t (0.0-1.0) on the path.

        See the linear interpolation math in bezier.py.

        """
        if self._segments is None:
            self._segments = bezier.length(self, segmented=True, n=10)

        return bezier.point(self, t, segments=self._segments)

    def points(self, amount=2, start=0.0, end=1.0):
        """Return a list of PathElements along the path.

        To omit the last point on closed paths: end=1-1.0/amount

        """
        if self._segments is None:
            self._segments = bezier.length(self, segmented=True, n=10)

        return bezier.points(self, amount, start, end, segments=self._segments)

    def addpoint(self, t):
        """Inserts a new PathElement at time t (0.0-1.0) on the path."""
        self._segments = None
        self._index = {}
        return bezier.insert_point(self, t)

    split = addpoint

    @property
    def length(self, precision=10):
        """Return an approximation of the total length of the path."""
        return bezier.length(self, segmented=False, n=precision)

    @property
    def contours(self):
        """Return a list of contours (i.e. segments separated by a MOVETO) in the path.

        Each contour is a BezierPath object.

        """
        return bezier.contours(self)

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
            return geometry.point_in_polygon(self._polygon[0], x, y)

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


def drawpath(path, **kwargs):
    """Draw the given BezierPath (or list of PathElements).

    The current stroke, strokewidth and fill color are applied.

    """
    if not isinstance(path, BezierPath):
        path = BezierPath(path)
    path.draw(**kwargs)


_autoclosepath = True
def autoclosepath(close=False):
    """Paths constructed with beginpath() and endpath() are automatically closed.
    """
    global _autoclosepath
    _autoclosepath = close


_path = None
def beginpath(x, y):
    """Start a new path at (x,y).

    The commands moveto(), lineto(), curveto() and closepath() can then be used
    between beginpath() and endpath() calls.

    """
    global _path
    _path = BezierPath()
    _path.moveto(x, y)


def moveto(x, y):
    """Move the current point in the current path to (x,y)."""
    if _path is None:
        raise NoCurrentPath

    _path.moveto(x, y)


def lineto(x, y):
    """Draw a line from the current point in the current path to (x,y)."""
    if _path is None:
        raise NoCurrentPath

    _path.lineto(x, y)


def curveto(x1, y1, x2, y2, x3, y3):
    """Draw a curve from the current point in the current path to (x3,y3).

    The curvature is determined by control handles x1, y1 and x2, y2.

    """
    if _path is None:
        raise NoCurrentPath

    _path.curveto(x1, y1, x2, y2, x3, y3)


def closepath():
    """Close the current path with a straight line to the last MOVETO."""
    if _path is None:
        raise NoCurrentPath

    _path.closepath()


def endpath(draw=True, **kwargs):
    """Draw and return the current path.

    With draw=False, only returns the path so it can be manipulated and drawn
    with drawpath().

    """
    global _path, _autoclosepath

    if _path is None:
        raise NoCurrentPath

    if _autoclosepath is True:
        _path.closepath()

    if draw:
        _path.draw(**kwargs)

    p, _path = _path, None
    return p


def findpath(points, curvature=1.0):
    """Return a smooth BezierPath from the given list of (x,y)-tuples."""
    return bezier.findpath(list(points), curvature)


Path = BezierPath
