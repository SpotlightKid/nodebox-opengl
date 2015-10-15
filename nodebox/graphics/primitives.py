# -*- coding: utf-8 -*-
"""Drawing primitives: Point, line, rect, ellipse, arrow, star, triangle.

The fill and stroke are two different shapes put on top of each other.

"""

from __future__ import absolute_import

from math import cos, pi, sin

from pyglet.gl import *

from .bezier import BezierPath
from .caching import precompile
from .glext import *
from .geometry import Point, superformula
from .state import global_state as _g, state_mixin


__all__ = (
    'Point',
    'arrow',
    'ellipse',
    'fast_star',
    'line',
    'rect',
    'star',
    'supershape',
    'triangle'
)

ELLIPSE_SEGMENTS = 50
_ellipses = {}
_stars = {}  # TODO: LRU?


def line(x0, y0, x1, y1, **kwargs):
    """Draw a straight line from x0, y0 to x1, y1.

    The current stroke and strokewidth are applied.

    """
    fill, stroke, strokewidth, strokestyle = state_mixin(**kwargs)

    if stroke is not None and strokewidth > 0:
        glColor4f(stroke[0], stroke[1], stroke[2], stroke[3] * _g.alpha)
        glLineWidth(strokewidth)

        if strokestyle != _g.strokestyle:
            glLineDash(strokestyle)

        glBegin(GL_LINES)
        glVertex2f(x0, y0)
        glVertex2f(x1, y1)
        glEnd()


def rect(x, y, width, height, **kwargs):
    """Draw a rectangle with the bottom left corner at x, y.

    The current stroke, strokewidth and fill color are applied.

    """
    fill, stroke, strokewidth, strokestyle = state_mixin(**kwargs)

    if fill is not None:
        glColor4f(fill[0], fill[1], fill[2], fill[3] * _g.alpha)
        glRectf(x, y, x + width, y + height)

    if stroke is not None and strokewidth > 0:
        glLineWidth(strokewidth)
        glLineDash(strokestyle)
        glColor4f(stroke[0], stroke[1], stroke[2], stroke[3] * _g.alpha)
        # Note: this performs equally well as when using precompile().
        glBegin(GL_LINE_LOOP)
        glVertex2f(x, y)
        glVertex2f(x + width, y)
        glVertex2f(x + width, y + height)
        glVertex2f(x, y + height)
        glEnd()


def triangle(x1, y1, x2, y2, x3, y3, **kwargs):
    """Draw the triangle created by connecting the three given points.

    The current stroke, strokewidth and fill color are applied.

    """
    fill, stroke, strokewidth, strokestyle = state_mixin(**kwargs)

    for i, clr in enumerate((fill, stroke)):
        if clr is not None and (i == 0 or strokewidth > 0):
            if i == 1:
                glLineWidth(strokewidth)

                if strokestyle != _g.strokestyle:
                    glLineDash(strokestyle)

            glColor4f(clr[0], clr[1], clr[2], clr[3] * _g.alpha)
            # Note: this performs equally well as when using precompile().
            glBegin((GL_TRIANGLES, GL_LINE_LOOP)[i])
            glVertex2f(x1, y1)
            glVertex2f(x2, y2)
            glVertex2f(x3, y3)
            glEnd()


def ellipse(x, y, width, height, segments=ELLIPSE_SEGMENTS, **kwargs):
    """Draw an ellipse with the center located at x, y.

    The current stroke, strokewidth and fill color are applied.

    """
    if segments not in _ellipses:
        # For the given amount of line segments, calculate the ellipse once.
        # Then reuse the cached ellipse by scaling it to the desired size.
        commands = []
        f = 2 * pi / segments
        v = [(cos(t) / 2, sin(t) / 2)
             for t in [i * f for i in list(range(segments)) + [0]]]

        for mode in (GL_TRIANGLE_FAN, GL_LINE_LOOP):
            commands.append(precompile(lambda:
                (glBegin(mode), [glVertex2f(x, y) for (x, y) in v], glEnd())))

        _ellipses[segments] = commands

    fill, stroke, strokewidth, strokestyle = state_mixin(**kwargs)

    for i, clr in enumerate((fill, stroke)):
        if clr is not None and (i == 0 or strokewidth > 0):
            if i == 1:
                glLineWidth(strokewidth)

                if strokestyle != _g.strokestyle:
                    glLineDash(strokestyle)

            glColor4f(clr[0], clr[1], clr[2], clr[3] * _g.alpha)
            glPushMatrix()
            glTranslatef(x, y, 0)
            glScalef(width, height, 1)
            glCallList(_ellipses[segments][i])
            glPopMatrix()


oval = ellipse  # Backwards compatibility.


def arrow(x, y, width, **kwargs):
    """Draw an arrow with its tip located at x, y.

    The current stroke, strokewidth and fill color are applied.

    """
    head = width * 0.4
    tail = width * 0.2
    fill, stroke, strokewidth, strokestyle = state_mixin(**kwargs)

    for i, clr in enumerate((fill, stroke)):
        if clr is not None and (i == 0 or strokewidth > 0):
            if i == 1:
                glLineWidth(strokewidth)
                glLineDash(strokestyle)

            glColor4f(clr[0], clr[1], clr[2], clr[3] * _g.alpha)
            # Note: this performs equally well as when using precompile().
            glBegin((GL_POLYGON, GL_LINE_LOOP)[i])
            glVertex2f(x, y)
            glVertex2f(x - head, y + head)
            glVertex2f(x - head, y + tail)
            glVertex2f(x - width, y + tail)
            glVertex2f(x - width, y - tail)
            glVertex2f(x - head, y - tail)
            glVertex2f(x - head, y - head)
            glVertex2f(x, y)
            glEnd()


def _gcd(a, b):
    """Return greatest common divider of a and b."""
    return _gcd(b, a % b) if b else a


def fast_star(x, y, points=20, outer=100, inner=50, **kwargs):
    """Draw a star with the given points, outer radius and inner radius.

    The current stroke, strokewidth and fill color are applied.

    """
    scale = _gcd(inner, outer)
    iscale = inner / scale
    oscale = outer / scale
    cached = _stars.get((points, iscale, oscale), [])

    if not cached:
        # which radius?
        radii = [oscale, iscale] * int(points + 1)
        radii.pop()
        f = pi / points
        v = [(r * sin(i * f), r * cos(i * f)) for i, r in enumerate(radii)]
        cached.append(precompile(lambda: (
            glBegin(GL_TRIANGLE_FAN),
            glVertex2f(0, 0),
            [glVertex2f(vx, vy) for (vx, vy) in v],
            glEnd()
        )))
        cached.append(precompile(lambda: (
            glBegin(GL_LINE_LOOP),
            [glVertex2f(vx, vy) for (vx, vy) in v],
            glEnd()
        )))
        _stars[(points, iscale, oscale)] = cached

    fill, stroke, strokewidth, strokestyle = state_mixin(**kwargs)

    for i, clr in enumerate((fill, stroke)):
        if clr is not None and (i == 0 or strokewidth > 0):
            if i == 1:
                glLineWidth(strokewidth)

                if strokestyle != _g.strokestyle:
                    glLineDash(strokestyle)

            glColor4f(clr[0], clr[1], clr[2], clr[3] * _g.alpha)
            glPushMatrix()
            glTranslatef(x, y, 0)
            glScalef(scale, scale, 1)
            glCallList(cached[i])
            glPopMatrix()


def star(x, y, points=20, outer=100, inner=50, **kwargs):
    """Draw a star with the given points, outer radius and inner radius.

    The current stroke, strokewidth and fill color are applied.

    This is about 20x slower than fast_star; use it only if you need the path
    returned.

    """
    p = BezierPath(**kwargs)
    p.moveto(x, y + outer)

    for i in range(0, int(2 * points) + 1):
        r = (outer, inner)[i % 2]
        a = pi * i / points
        p.lineto(x + r * sin(a), y + r * cos(a))

    p.closepath()

    if kwargs.get("draw", True):
        p.draw(**kwargs)

    return p


# -- SUPERSHAPE ---------------------------------------------------------------

def supershape(x, y, width, height, m, n1, n2, n3, points=100, percentage=1.0,
               range_=2 * pi, **kwargs):
    """Return a BezierPath constructed using the superformula.

    This formula can be used to describe many complex shapes and curves that
    are found in nature.

    """
    path = BezierPath()
    first = True

    for i in range(points):
        if i <= points * percentage:
            dx, dy = superformula(m, n1, n2, n3, i * range_ / points)
            dx, dy = dx * width / 2 + x, dy * height / 2 + y

            if first is True:
                path.moveto(dx, dy)
                first = False
            else:
                path.lineto(dx, dy)

    path.closepath()

    if kwargs.get("draw", True):
        path.draw(**kwargs)

    return path
