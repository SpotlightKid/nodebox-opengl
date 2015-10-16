# -*- coding: utf-8 -*-
# -- TESSELLATION -------------------------------------------------------------
# OpenGL can only display simple convex polygons directly.
# A polygon is simple if the edges intersect only at vertices, there are no
# duplicate vertices, and exactly two edges meet at any vertex.
# Polygons containing holes or polygons with intersecting edges must first be
# subdivided into simple convex polygons before they can be displayed.
# Such subdivision is called tessellation.

# Algorithm adopted from Squirtle:
#
#  Copyright (c) 2008 Martin O'Leary.
#
#  All rights reserved.
#
#  Redistribution and use in source and binary forms, with or without modification,
#  are permitted provided that the following conditions are met:
#  * Redistributions of source code must retain the above copyright notice,
#    this list of conditions and the following disclaimer.
#  * Redistributions in binary form must reproduce the above copyright notice,
#    this list of conditions and the following disclaimer in the documentation
#    and/or other materials provided with the distribution.
#  * Neither the name(s) of the copyright holders nor the names of its contributors may be used to
#    endorse or promote products derived from this software without specific prior written permission.
#
#  THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES,
#  INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A
#  PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDERS BE LIABLE FOR ANY DIRECT,
#  INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO,
#  PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION)
#  HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
#  (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE,
#  EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

from sys import platform
from ctypes import CFUNCTYPE, POINTER, byref, cast, pointer
from ctypes import CFUNCTYPE as _CFUNCTYPE
from pyglet.gl import \
    GLdouble, GLvoid, GLenum, GLfloat, \
    gluNewTess, gluTessProperty, gluTessNormal, gluTessCallback, gluTessVertex, \
    gluTessBeginPolygon, gluTessEndPolygon, \
    gluTessBeginContour, gluTessEndContour, \
    GLU_TESS_WINDING_RULE, GLU_TESS_WINDING_NONZERO, \
    GLU_TESS_VERTEX, GLU_TESS_BEGIN, GLU_TESS_END, GLU_TESS_ERROR, GLU_TESS_COMBINE, \
    GL_TRIANGLE_FAN, GL_TRIANGLE_STRIP, GL_TRIANGLES, GL_LINE_LOOP

if platform == "win32":
    from ctypes import WINFUNCTYPE as CFUNCTYPE

__all__ = (
    'Tessalate',
    'TessallationError',
    'tessallate'
)

_tessellator = gluNewTess()

# Winding rule determines the regions that should be filled and those that should remain unshaded.
# Winding direction is determined by the normal.
gluTessProperty(_tessellator, GLU_TESS_WINDING_RULE, GLU_TESS_WINDING_NONZERO)
gluTessNormal(_tessellator, 0, 0, 1)

# As tessellation proceeds, callback routines are called in a manner
# similar to OpenGL commands glBegin(), glEdgeFlag*(), glVertex*(), and glEnd().
# The callback functions must be C functions so we need to cast our Python callbacks to C.
_tessellate_callback_type = {
    GLU_TESS_VERTEX  : CFUNCTYPE(None, POINTER(GLvoid)),
    GLU_TESS_BEGIN   : CFUNCTYPE(None, GLenum),
    GLU_TESS_END     : CFUNCTYPE(None),
    GLU_TESS_ERROR   : CFUNCTYPE(None, GLenum),
    GLU_TESS_COMBINE : CFUNCTYPE(None,
        POINTER(GLdouble),
        POINTER(POINTER(GLvoid)),
        POINTER(GLfloat),
        POINTER(POINTER(GLvoid)))
}

# One path with a 100 points is somewhere around 15KB.
TESSELLATION_CACHE = 100


class TessellationError(Exception):
    pass


class Tessellate(list):
    """Tessellation state that stores data from the callback functions while
    tessellate() is processing.

    """
    def __init__(self):
        self.cache = {}         # Cache of previously triangulated contours
        self.queue = []         # Latest contours appear at the end of the list.
        self.reset()

    def clear(self):
        list.__init__(self, []) # Populated during _tessellate_vertex().

    def reset(self):
        self.clear()
        self.mode      = None   # GL_TRIANGLE_FAN | GL_TRIANGLE_STRIP | GL_TRIANGLES.
        self.triangles = []     # After tessellation, contains lists of (x,y)-vertices,
        self._combined = []     # which can be drawn with glBegin(GL_TRIANGLES) mode.


_tessellate = Tessellate()


def _tessellate_callback(type):
    # Registers a C version of a Python callback function for gluTessCallback().
    def _C(function):
        f = _tessellate_callback_type[type](function)
        gluTessCallback(_tessellator, type, cast(f, _CFUNCTYPE(None)))
        return f

    return _C


@_tessellate_callback(GLU_TESS_BEGIN)
def _tessellate_begin(mode):
    # Called to indicate the start of a triangle.
    _tessellate.mode = mode


@_tessellate_callback(GLU_TESS_VERTEX)
def _tessellate_vertex(vertex):
    # Called to define the vertices of triangles created by the tessellation.
    _tessellate.append(list(cast(vertex, POINTER(GLdouble))[0:2]))


@_tessellate_callback(GLU_TESS_END)
def _tessellate_end():
    # Called to indicate the end of a primitive.
    # GL_TRIANGLE_FAN defines triangles with a same origin (pt1).
    if _tessellate.mode in (GL_TRIANGLE_FAN, GL_TRIANGLE_STRIP):
        pt1 = _tessellate.pop(0)
        pt2 = _tessellate.pop(0)

        while _tessellate:
            pt3 = _tessellate.pop(0)
            _tessellate.triangles.extend([pt1, pt2, pt3])

            if _tessellate.mode == GL_TRIANGLE_STRIP:
                pt1 = pt2

            pt2 = pt3
    elif _tessellate.mode == GL_TRIANGLES:
        _tessellate.triangles.extend(_tessellate)
    elif _tessellate.mode == GL_LINE_LOOP:
        pass

    _tessellate.mode  = None
    _tessellate.clear()


@_tessellate_callback(GLU_TESS_COMBINE)
def _tessellate_combine(coords, vertex_data, weights, dataOut):
    # Called when the tessellation detects an intersection.
    x, y, z = coords[0:3]
    data = (GLdouble * 3)(x, y, z)
    dataOut[0] = cast(pointer(data), POINTER(GLvoid))
    _tessellate._combined.append(data)


@_tessellate_callback(GLU_TESS_ERROR)
def _tessellate_error(code):
    # Called when an error occurs.
    e, s, i = gluErrorString(code), "", 0

    while e[i]:
        s += chr(e[i])
        i += 1

    raise TessellationError(s)


_cache = {}


def tessellate(contours):
    """Return a list of triangulated (x,y)-vertices from the given list of path
    contours, where each contour is a list of (x,y)-tuples.

    The vertices can be drawn with GL_TRIANGLES to render a complex polygon,
    for example:

        glBegin(GL_TRIANGLES)
        for x, y in tessellate(contours):
            glVertex3f(x, y, 0)
        glEnd()
    """
    id = repr(contours)

    if id in _tessellate.cache:
        return _tessellate.cache[id]

    # Push the given contours to C and call gluTessVertex().
    _tessellate.reset()
    contours = [[(GLdouble * 3)(x, y, 0) for x, y in points] for points in contours]
    gluTessBeginPolygon(_tessellator, None)

    for vertices in contours:
        gluTessBeginContour(_tessellator)

        for v in vertices:
            gluTessVertex(_tessellator, v, v)

        gluTessEndContour(_tessellator)

    gluTessEndPolygon(_tessellator)

    # Update the tessellation cache with the results.
    if len(_tessellate.cache) > TESSELLATION_CACHE:
        del _tessellate.cache[_tessellate.queue.pop(0)]

    _tessellate.queue.append(id)
    _tessellate.cache[id] = _tessellate.triangles
    return _tessellate.triangles
