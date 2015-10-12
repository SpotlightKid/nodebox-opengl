#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Classes and functions for working with and transforming colors."""

__all__ = (
    'HSB',
    'LAB',
    'RGB',
    'XYZ',
    'Color',
    'analog',
    'colorplane',
    'complement',
    'darker',
    'hsb_to_rgb',
    'lab_to_rgb',
    'lighter',
    'luminance',
    'rgb_to_hsb',
    'rgb_to_lab',
    'rgb_to_xyz',
    'rotate_ryb',
    'xyz_to_rgb'
)

# Color systems
RGB = "RGB"
HSB = "HSB"
XYZ = "XYZ"
LAB = "LAB"


class Color(list):
    """A color with RGBA channels, with channel values ranging between 0.0-1.0.
    """

    def __init__(self, *args, **kwargs):
        """Create color instance from given color values.

        Either takes four parameters (R,G,B,A), three parameters (R,G,B), two
        parameters (grayscale and alpha) or one parameter (grayscale or Color
        object).

        An optional base (default 1.0) parameter defines the range of the given
        parameters.

        An optional colorspace (default 'RGB') defines the color space of the
        given parameters.

        """
        # Values are supplied as a tuple.
        if len(args) == 1 and isinstance(args[0], (list, tuple)):
            args = args[0]

        # R, G, B and A.
        if len(args) == 4:
            r, g, b, a = args[0], args[1], args[2], args[3]
        # R, G and B.
        elif len(args) == 3:
            r, g, b, a = args[0], args[1], args[2], 1
        # Two values, grayscale and alpha.
        elif len(args) == 2:
            r, g, b, a = args[0], args[0], args[0], args[1]
        # One value, another color object.
        elif len(args) == 1 and isinstance(args[0], Color):
            r, g, b, a = args[0].r, args[0].g, args[0].b, args[0].a
        # One value, None.
        elif len(args) == 1 and args[0] is None:
            r, g, b, a = 0, 0, 0, 0
        # One value, grayscale.
        elif len(args) == 1:
            r, g, b, a = args[0], args[0], args[0], 1
        # No value, transparent black.
        elif len(args):
            r, g, b, a = 0, 0, 0, 0

        # Transform to base 1:
        base = float(kwargs.get("base", 1.0))
        if base != 1:
            r, g, b, a = [ch / base for ch in (r, g, b, a)]

        # Transform to color space RGB:
        colorspace = kwargs.get("colorspace")
        if colorspace and colorspace != RGB:
            if colorspace == HSB:
                r, g, b = hsb_to_rgb(r, g, b)
            if colorspace == XYZ:
                r, g, b = xyz_to_rgb(r, g, b)
            if colorspace == LAB:
                r, g, b = lab_to_rgb(r, g, b)

        list.__init__(self, [r, g, b, a])
        self._dirty = False

    def __setitem__(self, i, v):
        list.__setitem__(self, i, v)
        self._dirty = True

    @property
    def red(self):
        return self[0]

    @property
    def green(self):
        return self[1]

    @property
    def blue(self):
        return self[2]

    @property
    def alpha(self):
        return self[3]

    @red.setter
    def red(self, v):
        self[0] = v

    @green.setter
    def green(self, v):
        self[1] = v

    @blue.setter
    def blue(self, v):
        self[2] = v

    @alpha.setter
    def alpha(self, v):
        self[3] = v

    r = red
    g = green
    b = blue
    a = alpha

    @property
    def rgb(self):
        return self[0], self[1], self[2]

    @rgb.setter
    def rgb(self, v):
        self[0] = v[0]
        self[1] = v[1]
        self[2] = v[2]

    @property
    def rgba(self):
        return self[0], self[1], self[2], self[3]

    @rgba.setter
    def rgba(self, v):
        self[0] = v[0]
        self[1] = v[1]
        self[2] = v[2]
        self[3] = v[3]

    def copy(self):
        return Color(self)

    def _apply(self):
        glColor4f(self[0], self[1], self[2], self[3] * _alpha)

    def __repr__(self):
        return "Color(%.3f, %.3f, %.3f, %.3f)" % \
            (self[0], self[1], self[2], self[3])

    def __eq__(self, clr):
        if not isinstance(clr, Color):
            return False

        return (self[0] == clr[0]
                and self[1] == clr[1]
                and self[2] == clr[2]
                and self[3] == clr[3])

    def __ne__(self, clr):
        return not self.__eq__(clr)

    def map(self, base=1.0, colorspace=RGB):
        """Return a list of RGBA values mapped to the given base.

        E.g. color values have the range 0-255 instead of 0.0-1.0, which is
        useful for setting image pixels.

        Other values than RGBA can be obtained by setting the colorspace
        (RGB/HSB/XYZ/LAB).

        """
        r, g, b, a = self

        if colorspace != RGB:
            if colorspace == HSB:
                r, g, b = rgb_to_hsb(r, g, b)
            if colorspace == XYZ:
                r, g, b = rgb_to_xyz(r, g, b)
            if colorspace == LAB:
                r, g, b = rgb_to_lab(r, g, b)

        if base != 1:
            r, g, b, a = [ch*base for ch in (r, g, b, a)]

        if base != 1 and isinstance(base, int):
            r, g, b, a = [int(ch) for ch in (r, g, b, a)]

        return r, g, b, a

    def blend(self, clr, t=0.5, colorspace=RGB):
        """Return a new color between this one and the given color.

        Parameter t is the amount to interpolate between the two colors (0.0
        equals the first color, 0.5 is half-way in between, etc.).

        Blending in CIE-LAB colorspace avoids "muddy" colors in the middle of
        the blend.

        """
        ch = zip(self.map(1, colorspace)[:3], clr.map(1, colorspace)[:3])
        r, g, b = [geometry.lerp(a, b, t) for a, b in ch]
        a = geometry.lerp(self.a, len(clr)==4 and clr[3] or 1, t)
        return Color(r, g, b, a, colorspace=colorspace)

    def rotate(self, angle):
        """Return a new color with it's hue rotated on the RYB color wheel."""
        h, s, b = rgb_to_hsb(*self[:3])
        h, s, b = rotate_ryb(h, s, b, angle)
        return Color(h, s, b, self.a, colorspace=HSB)


# -- COLOR SPACE --------------------------------------------------------------
# Transformations between RGB, HSB, CIE XYZ and CIE LAB color spaces.
# http://www.easyrgb.com/math.php

def rgb_to_hsb(r, g, b):
    """Convert the given RGB values to HSB (between 0.0-1.0)."""
    h, s, v = 0, 0, max(r, g, b)
    d = v - min(r, g, b)

    if v != 0:
        s = d / float(v)

    if s != 0:
        if   r == v: h = 0 + (g-b) / d
        elif g == v: h = 2 + (b-r) / d
        else       : h = 4 + (r-g) / d

    h = h / 6.0 % 1
    return h, s, v


def hsb_to_rgb(h, s, v):
    """Convert the given HSB color values to RGB (between 0.0-1.0)."""
    if s == 0:
        return v, v, v

    h = h % 1 * 6.0
    i = floor(h)
    f = h - i
    x = v * (1-s)
    y = v * (1-s * f)
    z = v * (1-s * (1-f))

    if i > 4:
        return v, x, y

    return [(v,z,x), (y,v,x), (x,v,z), (x,y,v), (z,x,v)][int(i)]


def rgb_to_xyz(r, g, b):
    """Convert the given RGB values to CIE XYZ (between 0.0-1.0)."""
    r, g, b = [((ch + 0.055) / 1.055) ** 2.4 if ch > 0.04045 else ch / 12.92
               for ch in (r, g, b)]
    r, g, b = [ch * 100.0 for ch in (r, g, b)]
    r, g, b = ( # Observer = 2, Illuminant = D65
        r * 0.4124 + g * 0.3576 + b * 0.1805,
        r * 0.2126 + g * 0.7152 + b * 0.0722,
        r * 0.0193 + g * 0.1192 + b * 0.9505)

    return r/95.047, g/100.0, b/108.883


def xyz_to_rgb(x, y, z):
    """Convert the given CIE XYZ color values to RGB (between 0.0-1.0)."""
    x, y, z = x*95.047, y*100.0, z*108.883
    x, y, z = [ch / 100.0 for ch in (x, y, z)]
    r = x *  3.2406 + y * -1.5372 + z * -0.4986
    g = x * -0.9689 + y *  1.8758 + z *  0.0415
    b = x * -0.0557 + y * -0.2040 + z *  1.0570
    r, g, b = [1.055 * ch**(1/2.4) - 0.055 if ch > 0.0031308 else ch * 12.92
              for ch in (r, g, b)]
    return r, g, b


def rgb_to_lab(r, g, b):
    """Convert the given RGB values to CIE LAB (between 0.0-1.0)."""
    x, y, z = rgb_to_xyz(r, g, b)
    x, y, z = [ch ** (1/3.0) if ch > 0.008856 else (ch * 7.787 + 16 / 116.0)
               for ch in (x, y, z)]
    l, a, b = y * 116 - 16, 500 * (x - y), 200 * (y - z)
    l, a, b = l / 100.0, (a + 86) / (86 + 98), (b + 108) / (108 + 94)
    return l, a, b


def lab_to_rgb(l, a, b):
    """Convert the given CIE LAB color values to RGB (between 0.0-1.0)."""
    l, a, b = l * 100, a * (86 + 98) - 86, b * (108 + 94) - 108
    y = (l + 16) / 116.0
    x = y + a / 500.0
    z = y - b / 200.0
    x, y, z = [ch**3 if ch**3 > 0.008856 else (ch - 16 / 116.0) / 7.787
               for ch in (x, y, z)]
    return xyz_to_rgb(x, y, z)


def luminance(r, g, b):
    """Return an indication (0.0-1.0) of how bright the color appears."""
    return (r * 0.2125 + g * 0.7154 + b + 0.0721) * 0.5


def darker(clr, step=0.2):
    """Return a copy of the color with a darker brightness."""
    h, s, b = rgb_to_hsb(clr.r, clr.g, clr.b)
    r, g, b = hsb_to_rgb(h, s, max(0, b - step))
    return Color(r, g, b, clr[3] if len(clr) == 4 else 1)


def lighter(clr, step=0.2):
    """Return a copy of the color with a lighter brightness."""
    h, s, b = rgb_to_hsb(clr.r, clr.g, clr.b)
    r, g, b = hsb_to_rgb(h, s, min(1, b + step))
    return Color(r, g, b, clr[3] if len(clr) == 4 else 1)


darken, lighten = darker, lighter


# -- COLOR ROTATION -----------------------------------------------------------

# Approximation of the RYB color wheel.
# In HSB, colors hues range from 0 to 360,
# but on the color wheel these values are not evenly distributed.
# The second tuple value contains the actual value on the wheel (angle).
_colorwheel = [
    (  0,   0), ( 15,   8), ( 30,  17), ( 45,  26),
    ( 60,  34), ( 75,  41), ( 90,  48), (105,  54),
    (120,  60), (135,  81), (150, 103), (165, 123),
    (180, 138), (195, 155), (210, 171), (225, 187),
    (240, 204), (255, 219), (270, 234), (285, 251),
    (300, 267), (315, 282), (330, 298), (345, 329), (360, 360)
]

def rotate_ryb(h, s, b, angle=180):
    """Rotate the given HSB color (0.0-1.0) on the RYB color wheel.

    The RYB colorwheel is not mathematically precise, but focuses on
    aesthetically pleasing complementary colors.

    """
    h = h*360 % 360
    # Find the location (angle) of the hue on the RYB color wheel.
    for i in range(len(_colorwheel) - 1):
        (x0, y0), (x1, y1) = _colorwheel[i], _colorwheel[i + 1]
        if y0 <= h <= y1:
            a = geometry.lerp(x0, x1, t=(h - y0) / (y1 - y0))
            break

    # Rotate the angle and retrieve the hue.
    a = (a + angle) % 360
    for i in range(len(_colorwheel) - 1):
        (x0, y0), (x1, y1) = _colorwheel[i], _colorwheel[i + 1]
        if x0 <= a <= x1:
            h = geometry.lerp(y0, y1, t=(a - x0) / (x1 - x0))
            break

    return h / 360.0, s, b


def complement(clr):
    """Return the color on the opposite side of the color wheel.

    The complementary color contrasts with the given color.

    """
    if not isinstance(clr, Color):
        clr = Color(clr)

    return clr.rotate(180)


def analog(clr, angle=20, d=0.1):
    """Return a random adjacent color on the color wheel.

    Analogous color schemes can often be found in nature.

    """
    h, s, b = rgb_to_hsb(*clr[:3])
    h, s, b = rotate_ryb(h, s, b, angle=random(-angle, angle))
    s *= 1 - random(-d, d)
    b *= 1 - random(-d, d)
    return Color(h, s, b, clr[3] if len(clr) == 4 else 1, colorspace=HSB)


# -- COLOR PLANE --------------------------------------------------------------
# Not part of the standard API but too convenient to leave out.

def colorplane(x, y, width, height, *a):
    """Draw a rectangle that emits a different fill color from each corner.

    An optional number of colors can be given:

    - four colors define top left, top right, bottom right and bottom left,
    - three colors define top left, top right and bottom,
    - two colors define top and bottom,
    - no colors assumes black top and white bottom gradient.

    """
    if len(a) == 2:
        # Top and bottom colors.
        clr1, clr2, clr3, clr4 = a[0], a[0], a[1], a[1]
    elif len(a) == 4:
        # Top left, top right, bottom right, bottom left.
        clr1, clr2, clr3, clr4 = a[0], a[1], a[2], a[3]
    elif len(a) == 3:
        # Top left, top right, bottom.
        clr1, clr2, clr3, clr4 = a[0], a[1], a[2], a[2]
    elif len(a) == 0:
        # Black top, white bottom.
        clr1 = clr2 = (0,0,0,1)
        clr3 = clr4 = (1,1,1,1)

    glPushMatrix()
    glTranslatef(x, y, 0)
    glScalef(width, height, 1)
    glBegin(GL_QUADS)
    glColor4f(clr1[0], clr1[1], clr1[2], clr1[3] * _alpha)
    glVertex2f(-0.0,  1.0)
    glColor4f(clr2[0], clr2[1], clr2[2], clr2[3] * _alpha)
    glVertex2f( 1.0,  1.0)
    glColor4f(clr3[0], clr3[1], clr3[2], clr3[3] * _alpha)
    glVertex2f( 1.0, -0.0)
    glColor4f(clr4[0], clr4[1], clr4[2], clr4[3] * _alpha)
    glVertex2f(-0.0, -0.0)
    glEnd()
    glPopMatrix()
