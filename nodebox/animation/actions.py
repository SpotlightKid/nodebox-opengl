# -*- coding: utf-8 -*-
"""Actions encapsulate transformations on the attributes of a target.

They allow, for example, to change a property of a Layer, say its width,
gradually over a period of time, to achieve animation effects.

The concept is "borrowed" from the cocos2d framework. For now, see their
documentation on the matter here:

http://python.cocos2d.org/doc/programming_guide/actions.html

"""

from __future__ import absolute_import, print_function, unicode_literals

import copy
import time

from functools import partial

from .tween import *
from ..graphics.geometry import clamp


__all__ = (
    'Action',
    'Actionable',
    'Fade',
    'FadeIn',
    'FadeOut',
    'MoveBy',
    'MoveByX',
    'MoveByY',
    'MoveTo',
    'MoveToX',
    'MoveToY',
    'IntervalAction',
    'SetAttributesAction',
    'test'
)


class Action(object):
    """The most general action."""

    def __init__(self, *args, **kwargs):
        """Do not override - use setup."""
        self.duration = None
        # The base action has potentially infinite duration
        self.setup(*args, **kwargs)
        # Actionable object that is the target of the action
        self.target = None
        self._elapsed = 0.0
        self._done = False

    def setup(*args, **kwargs):
        """Do set up for action.

        Gets called by __init__ with all the parameteres received.

        At this time the target for the action is unknown.
        Typical use is store parameters needed by the action.

        """
        pass

    def start(self):
        """Start the action.

        External code sets self.target and then calls this method.
        Perform here any extra initialization needed.

        """
        pass

    def stop(self):
        """Stop the action.

        When the action must cease to perform this function is called by
        external code; after this call no other method should be called.

        """
        self.target = None

    def update(self, dt=0.):
        """Advance the action state.

        Gets called every frame. `dt` is the time in seconds (float) that
        elapsed since the last call.

        """
        self._elapsed += dt

    @property
    def done(self):
        """False while the step method must be called."""
        return self._done


class IntervalAction(Action):
    """An action that lasts for a fixed duration.

    Interval Actions are the ones that have fixed duration, known when the
    worker instance is created, and, conceptually, the expected duration must
    be positive. Degeneratated cases, when a particular instance gets a zero
    duration, are allowed for convenience.

    IntervalAction adds the method ``advance`` to the public interfase, and it
    expresses the changes to target as a function of the time elapsed.

    """
    def update(self, dt=0.):
        self._elapsed += dt
        self.advance(self._elapsed)

    def advance(self, t):
        """Gets called every time the action should advance one step.

        't' is the time elapsed since update() was called the first time.

        Overwrite this in your concrete interval action class.

        """
        pass

    @property
    def done(self):
        """Action is done when the interval duration has elasped."""
        return self._elapsed >= self.duration


class SetAttributesAction(IntervalAction):
    """Change one or more attributes of the target over a time interval."""

    def setup(self, attr, destval=1.0, duration=1.0, tween=ease_linear,
              clamp=False, relative=False):
        """Initialize the action parameters.

        ``attr`` is the attribute of the action target to change over time.
        ``destval`` (default ``1.0``) is the destination value of this
        attribute that should be reached at the end of ``duration`` (in
        seconds, default ``1.0``).

        Both ``attr`` and ``destval`` can be either a single string resp. value
        or a tuple or list of values. If several attributes are given,
        ``destval`` should be a sequence of the same length or a single value,
        which will then be used as the destination value for each attribute.

        If ``relative`` is set to ``True`` (default ``False``), the destination
        value(s) is (are) not absolute, but relative to the value of the(ir)
        target attribute at the time of the start of the action.

        The default curve of the intermediate values is linear. You can specify
        a different tweening function with the ``tween`` keyword argument
        (default ``ease_linear``). The ``nodebox.animation.tween`` module
        provides a wide variety of tweening functions for differently weighted
        curves. If you want to provide your own custom tweening function, it
        needs to accept four parameters:

        * ``t`` - time elapsed (in seconds) going from zero to ``d``
        * ``b`` - start value
        * ``c`` - value change, i.e. ``destination value - start value``
        * ``d`` - total duration (in seconds)

        The function must return the intermediate value at time ``t``.

        If ``clamp`` is set to ``True`` all values are pinned between the start
        and the destination value, i.e. if the tweening function returns a
        value higher than the destination value, it is replaced by the latter
        and if it returns a value lower than the start value, the start value
        is used.

        """
        self.attr = attr if isinstance(attr, (tuple, list)) else (attr,)

        if isinstance(destval, (tuple, list)):
            self.destval = list(destval)
        else:
            self.destval = [destval] * len(self.attr)

        self.duration = duration
        self.tween = tween
        self.clamp = clamp
        self.relative = relative

    def start(self):
        self.startval = []
        self.interval = []

        for i, attr in enumerate(self.attr):
            startval = getattr(self.target, attr, 0.)

            if self.relative:
                self.destval[i] += startval

            self.startval.append(startval)
            self.interval.append(self.destval[i] - startval)

    def advance(self, t):
        for i, attr in enumerate(self.attr):
            try:
                if self.done:
                    value = self.destval[i]
                else:
                    value = self.tween(t, self.startval[i], self.interval[i],
                                       self.duration)

                if self.clamp:
                    value = clamp(value, self.startval[i], self.destval[i])
            except ZeroDivisionError:
                value = self.destval[i]

            setattr(self.target, attr, value)


class Fade(SetAttributesAction):
    """Fade the target in or out by modifying its opacity."""

    def setup(self, value, *args, **kwargs):
        """Fade the target in or out within given duration.

        The resulting opacity must be given as a float between 0.0 and 1.0.

        Duration should be given in seconds as a float and may also be zero
        for immediately setting the opacity to the destination value.

        """
        kwargs['clamp'] = True
        super(Fade, self).setup('opacity', clamp(value), *args, **kwargs)


FadeIn = partial(Fade, 1.)
FadeOut = partial(Fade, 0.)


class MoveTo(SetAttributesAction):
    """Move the action target to a given position."""

    def setup(self, pos=(0, 0), *args, **kwargs):
        """Move target to pos given a (x, y) tuple within given duration.

        Duration should be given in seconds as a float and may also be zero
        for immediate placement.

        """
        super(MoveTo, self).setup(('x', 'y'), pos, *args, **kwargs)


MoveToX = partial(SetAttributesAction, 'x')
MoveToY = partial(SetAttributesAction, 'y')
MoveBy = partial(MoveTo, relative=True)
MoveByX = partial(SetAttributesAction, 'x', relative=True)
MoveByY = partial(SetAttributesAction, 'y', relative=True)


class Actionable(object):
    """Mixin class to add to Layers that can have actions performed on them."""

    def do(self, action):
        """Add action to perform."""
        if not hasattr(self, '_actions'):
            self._actions = set([])

        action = copy.deepcopy(action)
        self._actions.add(action)
        action.target = self
        action.start()
        return action

    def remove_action(self, action):
        action.stop()
        action.target = None

        if not hasattr(self, '_to_remove'):
            self._to_remove = set([])

        self._to_remove.add(action)

    def update(self, dt=None):
        if dt is None:
            try:
                dt = self.canvas.elapsed
            except AttributeError:
                dt = 0.

        if not hasattr(self, '_to_remove'):
            self._to_remove = set([])

        self._actions = getattr(self, '_actions', set([])) - self._to_remove
        del self._to_remove

        for action in self._actions:
            action.update(dt)

            if action.done:
                self.remove_action(action)

    @property
    def done(self):
        """Return True when all transitions have finished."""
        for action in getattr(self, '_actions', set([])):
            if not action.done:
                return False
        else:
            return True


def test(n=100.0):
    a = Actionable()
    a.value = 0
    action = a.do(SetAttributeAction("value", n, 5.0, ease_in_expo))

    try:
        dt = 0
        while True:
            start = time.time()
            a.update(dt)
            time.sleep(0.1)
            print(a.value)
            if action.done:
                break
            dt = time.time() - start
    except KeyboardInterrupt:
        pass


if __name__ == '__main__':
    import sys
    try:
        test(float(sys.argv[1]))
    except:
        test()
