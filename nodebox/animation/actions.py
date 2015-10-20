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
    'ChangeAttributesAction',
    'Delay',
    'Fade',
    'FadeIn',
    'FadeOut',
    'Hide',
    'IntervalAction',
    'MoveBy',
    'MoveByX',
    'MoveByY',
    'MoveTo',
    'MoveToX',
    'MoveToY',
    'ParallelAction',
    'RepeatAction',
    'SequenceAction',
    'SetAttributesAction',
    'Show',
    'ToggleHidden'
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
        """False while the update method must be called."""
        return self._done

    def copy(self):
        return copy.deepcopy(self)


class Actionable(object):
    """Mixin class to add to Layers that can have actions performed on them."""

    def do(self, action):
        """Add action to perform."""
        if not hasattr(self, '_actions'):
            self._actions = set([])

        action = action.copy()
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
        """Return True when all actions have finished."""
        for action in getattr(self, '_actions', set([])):
            if not action.done:
                return False
        else:
            return True


class IntervalAction(Action):
    """An action that lasts for a fixed duration.

    Interval Actions are the ones that have fixed duration, known when the
    worker instance is created, and, conceptually, the expected duration must
    be positive. Degeneratated cases, when a particular instance gets a zero
    duration, are allowed for convenience.

    IntervalAction adds the method ``advance`` to the public interface, and it
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


class ChangeAttributesAction(IntervalAction):
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
        self.delta = []

        for i, attr in enumerate(self.attr):
            startval = getattr(self.target, attr, 0.)

            if callable(self.destval[i]):
                self.destval[i] = self.destval[i]()

            if self.relative:
                self.destval[i] += startval

            self.startval.append(startval)
            self.delta.append(self.destval[i] - startval)

    def advance(self, t):
        for i, attr in enumerate(self.attr):
            try:
                if self.done:
                    value = self.destval[i]
                else:
                    value = self.tween(t, self.startval[i], self.delta[i],
                                       self.duration)

                if self.clamp:
                    value = clamp(value, self.startval[i], self.destval[i])
            except ZeroDivisionError:
                value = self.destval[i]

            if self.target is not None:
                setattr(self.target, attr, value)


class SetAttributesAction(Action):
    """Set one or more attributes of the target to a given value immediately.
    """
    def setup(self, attr, destval=1., relative=False):
        """Initialize the action parameters.

        ``attr``, ``destval`` and ``relative`` have the same semantics as for
        the ``ChangeAttributesAction``, except that each attribute is set to
        it corresponding destination value immediately when the ``start``
        method of the action is called.

        """
        self.relative = relative
        self.attr = attr if isinstance(attr, (tuple, list)) else (attr,)

        if isinstance(destval, (tuple, list)):
            self.destval = list(destval)
        else:
            self.destval = [destval] * len(self.attr)

    def start(self):
        for i, attr in enumerate(self.attr):
            if callable(self.destval[i]):
                self.destval[i] = self.destval[i]()

            if self.relative:
                startval = getattr(self.target, attr, 0.)
                self.destval[i] += startval

            setattr(self.target, attr, self.destval[i])

        self._done = True


class SequenceAction(Action):
    """Execute a sequence of actions one after another."""

    def setup(self, *actions):
        """Set actions and current action to None"""
        self.actions = [action.copy() for action in actions]
        self.current = None

    def start(self):
        """Set current action to the first, set its target and start it."""
        self.current = 0
        self.actions[self.current].target = self.target
        self.actions[self.current].start()

    def update(self, dt=0.):
        if self.current is not None and self.actions[self.current].done:
            self.actions[self.current].stop()
            self.current += 1

            if self.current < len(self.actions):
                self.actions[self.current].target = self.target
                self.actions[self.current].start()
            else:
                self.current = None

        if self.current is not None:
            self.actions[self.current].update(dt)

    def stop(self):
        if self.current is not None:
            self.actions[self.current].stop()
            self.current = None

        super(SequenceAction, self).stop()

    @property
    def done(self):
        return self.current is None or (self.actions and self.actions[-1].done)


class ParallelAction(Action):
    """Execute a sequence of actions simultaneously."""

    def setup(self, *actions):
        """Set actions to given iterable"""
        self.actions = [action.copy() for action in actions]

    def start(self):
        for action in self.actions:
            action.target = self.target
            action.start()

    def update(self, dt=0.):
        for action in self.actions:
            if not action.done:
                action.update(dt)

    def stop(self):
        for action in self.actions:
            action.stop()
            action.target = None

    @property
    def done(self):
        return all(action.done for action in self.actions)


class Delay(IntervalAction):
    """Delays the action a certain amount of seconds."""

    def setup(self, delay):
        """Set delay to given amount in seconds (float or int)."""
        self.duration = delay


class RepeatAction(Action):
    """Repeat one action for n times or until stopped."""
    def setup(self, action, times=None):
        self.action = action
        self.times = times

    def start(self):
        self.current = self.action.copy()
        self.current.target = self.target
        self.current.start()

    def update(self, dt=0.):
        self._elapsed += dt
        self.current.update(dt)

        if self.current.done:
            self.current.stop()
            if self.times is not None:
                self.times -= 1

            if self.times == 0:
                self._done = True
            else:
                self.current = self.action.copy()
                self.current.target = self.target
                self.current.start()

    def stop(self):
        if not self._done:
            self.current.stop()
            self._done = True

        super(RepeatAction, self).stop()


class Fade(ChangeAttributesAction):
    """Fade the target in or out by modifying its opacity attribute."""

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


class Hide(Action):
    """Hide the target by setting it hidden attribute to True.

    To show it again call the `Show` action.

    """
    flag = True

    def start(self):
        self.target.hidden = self.flag
        self._done = True


class Show(Hide):
    """Hide the target by setting it hidden attribute to False.

    To hide it call the `Hide` action.

    """
    flag = False


class ToggleHidden(Action):
    """Toggle hidden attribute of the target."""
    def start(self):
        self.target.hidden = not self.target.hidden
        self._done = True


class MoveTo(ChangeAttributesAction):
    """Move the action target to a given position."""

    def setup(self, position=(0, 0), *args, **kwargs):
        """Move target to given position (x, y) tuple within given duration.

        Duration should be given in seconds as a float and may also be zero
        for immediate placement.

        """
        super(MoveTo, self).setup(('x', 'y'), position, *args, **kwargs)


MoveToX = partial(ChangeAttributesAction, 'x')
MoveToY = partial(ChangeAttributesAction, 'y')
MoveBy = partial(MoveTo, relative=True)
MoveByX = partial(ChangeAttributesAction, 'x', relative=True)
MoveByY = partial(ChangeAttributesAction, 'y', relative=True)


def _test(n=100.0):
    a = Actionable()
    a.value = 0
    action = a.do(ChangeAttributesAction("value", n, 5.0, ease_in_expo))

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
