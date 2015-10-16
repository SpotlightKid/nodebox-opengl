# -*- coding: utf-8 -*-
"""This an adaptation of Robert Penner's easing/tweening algorithms.

    http://www.robertpenner.com/easing/

Translated into Python by M.E.Farmer 2013. Made Python 3 compatible and
PEP-8-ified by Christopher Arndt 2015.

I couldn't find a good tweening library for a project I was working on so I
found the original tweening alogorithms and modified them for Python. Because
they are stateless I have included helper functions that make them easy to use.
They are implemented as generators so you can just setup and then call their
``.next()`` method or use them in for-loops.

Some of these tweens were created by me using the awesome demo at
http://www.timotheegroleau.com/Flash/experiments/easing_function_generator.htm

To create your own custom tween play with the demo and use the last line of the
formula. Copy the ``inch_worm tween`` and replace the return line with the one
the formula gives you. You can also use the ``custom_tween`` function: just
pass in the formula as a string and it will return a tweening function for you.
You just need what is between the return and the semicolon.

Where would you use these?

* calculate position changes with ease..ing ;)
* Robotics, game object movements, webpage scrolling, etc.
* LED or object color morphs are a snap
* "breathing" LED type effects
*  etc..

Example::

    >>> from tween import *
    >>> t = tween(ease_linear, 1, 255, 20, True, False, True)
    >>> list(t)
    [1, 14, 28, 41, 54, 68, 81, 95, 108, 121, 135, 148, 161, 175, 188, 202, 215, 228, 242, 255]

    >>> color1 = (123, 234, 12)
    >>> color2 = (255, 12, 189)
    >>> color_gen = color_tween(ease_in_quad, color1, color2, 10,
    ...                         include_begin=True, endless=False)
    >>> for rgb in color_gen:
    ...     print(rgb)
    (123, 234, 12)
    (125, 231, 14)
    (130, 223, 21)
    (138, 209, 32)
    (149, 190, 47)
    (164, 165, 67)
    (182, 135, 91)
    (203, 100, 119)
    (227, 59, 152)
    (255, 12, 189)

    >>> t = cycle_tween(ease_in_quad, ease_out_quad, 1, 255, 10, endless=False,
    ...                 round=True)
    >>> list(t)
    [1, 4, 11, 24, 42, 65, 92, 125, 164, 207, 255, 207, 164, 125, 92, 65, 42, 24, 11, 4, 1]

"""

from __future__ import absolute_import, division, print_function  # for doctests

import math

from functools import partial

from ..graphics.geometry import clamp

__all__ = (
    'color_tween',
    'custom_tween',
    'cycle_tween',
    'ease_in_circ',
    'ease_in_cubic',
    'ease_in_elastic_big',
    'ease_in_elastic_small',
    'ease_in_expo',
    'ease_in_quad',
    'ease_in_quartic',
    'ease_in_quintic',
    'ease_in_sine',
    'ease_inch_worm',
    'ease_inout_circ',
    'ease_inout_cubic',
    'ease_inout_expo',
    'ease_inout_quad',
    'ease_inout_quartic',
    'ease_inout_quintic',
    'ease_inout_sine',
    'ease_linear',
    'ease_loop',
    'ease_out_circ',
    'ease_out_cubic',
    'ease_out_elastic_big',
    'ease_out_elastic_small',
    'ease_out_expo',
    'ease_out_quad',
    'ease_out_quartic',
    'ease_out_quintic',
    'ease_out_sine',
    'float_tween',
    'tween',
    'xy_tween'
)


def tween(func, begin=0., end=1., steps=10, include_begin=False,
          endless=False, round=False):
    """Wrap a tweening function in a generator with a fixed number of steps.

    Yields ``steps`` number of values between ``begin`` and ``end``
    (inclusive), where the in-between values are determined by ``func``. If
    ``include_begin`` is ``True`` (default ``False``), the first value yielded
    is ``begin``. If ``endless`` is ``True`` (default ``False``), the generator
    yields the end value indefinitely, once the last step is reached.

    Use by itself or use it to create composite easing.

    Example:

        Create a function that takes an RGB tuple and tween each color channel
        using a different easing function.

        Create a function that tweens between X,Y pairs using a different
        easing function on each coordinate to give arced type trajectories.

    This generator yields floats unless ``round`` is ``True``, in which case
    all values are rounded and converted to the nearest integer.

    """
    change = float(end - begin)
    tick = 0.0

    if include_begin:
        steps -= 1
        yield int(round(begin)) if round else begin

    while tick < steps:
        tick += 1
        out = func(tick, begin, change, steps)
        out = int(round(out)) if round else out
        yield out

    while endless:
        yield out


float_tween = partial(tween, round=False)
int_tween = partial(tween, round=True)


def xy_tween(func, begin_xy=(0., 0.), end_xy=(1., 1.), steps=10,
             include_begin=False, endless=False, round=False):
    """Transition between (x, y) sequences using easing.

    endless = repeat last value forever once last step is reached

    This generator yields (x, y) tuplesc of floats unless ``round`` is
    ``True``, in which case all values are rounded and converted to the nearest
    integer.

    """
    change_x = float(end_xy[0] - begin_xy[0])
    change_y = float(end_xy[1] - begin_xy[1])
    tick = 0.0

    if include_begin:
        steps -= 1
        yield (int(round(begin_xy[0])) if round else begin_xy[0],
               int(round(begin_xy[1])) if round else begin_xy[1])

    while tick < steps:
        tick += 1
        x = func(tick, begin_xy[0], change_x, steps)
        y = func(tick, begin_xy[1], change_y, steps)
        x = int(round(x)) if round else x
        y = int(round(y)) if round else y
        yield (x, y)

    while endless:
        yield (x, y)


def color_tween(func, begin_rgb, end_rgb, steps, include_begin=False,
                endless=False):
    """Transition between RGB tuples or list with easing.

    Because functions that are 'elastic' can bounce above or below the min and
    max ranges (0, 255) we clamp the values between 0 and 255.

    endless = repeat last value forever once last step is reached

    This generator yields (r, g, b) tuples of integers.

    """
    change_r = end_rgb[0] - begin_rgb[0]
    change_g = end_rgb[1] - begin_rgb[1]
    change_b = end_rgb[2] - begin_rgb[2]
    tick = 0.0

    c = lambda v: clamp(v, 0, 255)

    if include_begin:
        steps -= 1
        r, g, b = begin_rgb
        yield (c(r), c(g), c(b))

    while tick < steps:
        tick += 1
        r = c(int(round(func(tick, begin_rgb[0], change_r, steps))))
        g = c(int(round(func(tick, begin_rgb[1], change_g, steps))))
        b = c(int(round(func(tick, begin_rgb[2], change_b, steps))))
        yield (r, b, g)

    while endless:
        yield (r, b, g)


def cycle_tween(func1, func2, begin=0., end=1., steps=10, endless=False,
                round=True):
    """Ease forward and backward through begin and end points

    Easing functions can be the same or different to
    give varied effects.

    endless = True is a repeating cycle
    endless = False is a single cycle

    This generator yields floats unless ``round`` is ``True``, in which case
    all values are rounded and converted to the nearest integer.

    """
    # add the first value so it will start right
    yield int(round(begin)) if round else begin

    while True:
        for step in tween(func1, begin, end, steps, False, False, round):
            yield step

        for step in tween(func2, end, begin, steps, False, False, round):
            yield step

        if not endless:
            break


def custom_tween(formula_string):
    """Function for creating your own custom tweens.

    Call this function with your formula string and it will return a tweening
    function for you to use.

    Go to this website:

       http://www.timotheegroleau.com/Flash/experiments/easing_function_generator.htm

    and tweak the control points and take the formula and pass it in as a
    string. You need everything between the return and the semicolon.

    This is a bounce tween for example::

        tween = custom_tween('''b + c * (26.65 * tc * ts + -91.5925 * ts * ts
            + 115.285 * tc + -62.89 * ts + 13.5475 * t)''')

    """
    def custom(t, b, c, d):
        t /= d
        ts = t * t
        tc = ts * t  # noqa
        return eval(formula_string)

    return custom


def ease_linear(t, b, c, d):
    v = t / d
    return c * v + b


def ease_in_quad(t, b, c, d):
    v = t / d
    return c * v * v + b


def ease_out_quad(t, b, c, d):
    v = t / d
    return -c * v * (v - 2) + b


def ease_inout_quad(t, b, c, d):
    v = t / (d / 2)

    if v < 1:
        return c * 2 * v * v + b
    else:
        v -= 1
        return -c * 2 * (v * (v - 2) - 1) + b


def ease_in_cubic(t, b, c, d):
    v = t / d
    return c * pow(v, 3) + b


def ease_out_cubic(t, b, c, d):
    v = t / d
    return c * (pow(v - 1, 3) + 1) + b


def ease_inout_cubic(t, b, c, d):
    v = t / (d / 2)

    if v < 1:
        return c * 2 * pow(v, 3) + b
    else:
        return c * 2 * (pow(v - 2, 3) + 2) + b


def ease_in_quartic(t, b, c, d):
    v = t / d
    return c * pow(v, 4) + b


def ease_out_quartic(t, b, c, d):
    v = t / d
    return -c * (pow(v - 1, 4) - 1) + b


def ease_inout_quartic(t, b, c, d):
    v = t / (d / 2)

    if v < 1:
        return c * 2 * pow(v, 4) + b
    else:
        return -c * 2 * (pow(v - 2, 4) - 2) + b


def ease_in_quintic(t, b, c, d):
    v = t / d
    return c * pow(v, 5) + b


def ease_out_quintic(t, b, c, d):
    v = t / d
    return c * (pow(v - 1, 5) + 1) + b


def ease_inout_quintic(t, b, c, d):
    v = t / (d / 2)

    if v < 1:
        return c * 2 * pow(v, 5) + b
    else:
        return c * 2 * (pow(v - 2, 5) + 2) + b


def ease_in_sine(t, b, c, d):
    v = t / d
    return c * (1 - math.cos(v * (math.pi / 2))) + b


def ease_out_sine(t, b, c, d):
    v = t / d
    return c * math.sin(v * (math.pi / 2)) + b


def ease_inout_sine(t, b, c, d):
    v = t / d
    return c * 2 * (1 - math.cos(math.pi * v)) + b


def ease_in_expo(t, b, c, d):
    v = t / d
    return c * pow(2, 10 * (v - 1)) + b


def ease_out_expo(t, b, c, d):
    v = t / d
    return c * (-pow(2, -10 * v) + 1) + b


def ease_inout_expo(t, b, c, d):
    v = t / (d / 2)

    if v < 1:
        return c / 2 * pow(2, 10 * (v - 1)) + b
    else:
        v -= 1
        return c / 2 * (-pow(2, -10 * v) + 2) + b


def ease_in_circ(t, b, c, d):
    v = t / d
    return c * (1 - math.sqrt(1 - v * v)) + b


def ease_out_circ(t, b, c, d):
    v = t / d - 1
    return c * math.sqrt(1 - v * v) + b


def ease_inout_circ(t, b, c, d):
    v = t / (d / 2)

    if v < 1:
        return c / 2 * (1 - math.sqrt(1 - v * v)) + b
    else:
        v -= 2
        return c / 2 * (math.sqrt(1 - v * v) + 1) + b


def ease_in_elastic_big(t, b, c, d):
    t /= d
    ts = t * t
    tc = ts * t
    return b + c * (56 * tc * ts + -105 * ts * ts + 60 * tc + -10 * ts)


def ease_out_elastic_big(t, b, c, d):
    t /= d
    ts = t * t
    tc = ts * t
    return b + c * (
        56 * tc * ts + -175 * ts * ts + 200 * tc + -100 * ts + 20 * t)


def ease_in_elastic_small(t, b, c, d):
    t /= d
    ts = t * t
    tc = ts * t
    return b + c * (33 * tc * ts + -59 * ts * ts + 32 * tc + -5 * ts)


def ease_out_elastic_small(t, b, c, d):
    t /= d
    ts = t * t
    tc = ts * t
    return b + c * (
        33 * tc * ts + -106 * ts * ts + 126 * tc + -67 * ts + 15 * t)


def ease_loop(t, b, c, d):
    t /= d
    ts = t * t
    tc = ts * t
    return b + c * (-11.945 * tc * ts + 45.585 * ts * ts + -42.685 * tc +
                    5.795 * ts + 4.25 * t)


def ease_inch_worm(t, b, c, d):
    t /= d
    ts = t * t
    tc = ts * t
    return b + c * (44.2925 * tc * ts + -114.88 * ts * ts + 105.18 *
                    tc + -39.99 * ts + 6.3975 * t)
