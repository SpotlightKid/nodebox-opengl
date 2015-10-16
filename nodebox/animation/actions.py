# -*- coding: utf-8 -*-

from __future__ import absolute_import, print_function, unicode_literals

import copy
import time

from .tween import *
from ..graphics.geometry import clamp


__all__ = (
    'Action',
    'Actionable',
    'IntervalAction',
    'SetAttributeAction',
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

        Gets called by __init__ with all the parameteres received,

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

    def update(self, dt):
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
    def update(self, dt):
        self._elapsed += dt
        self.advance(self._elapsed)

    def advance(self, t):
        """Gets called every time the action should advance one step.

        't' is the time elapsed normalized to [0, 1]

        If this action takes 5 seconds to execute, `t` will be equal to 0
        at 0 seconds. `t` will be 0.5 at 2.5 seconds and `t` will be 1 at 5sec.

        """
        pass

    @property
    def done(self):
        return self._elapsed >= self.duration


class SetAttributeAction(IntervalAction):
    """Changes an attribute of the target until a destination value is reached.
    """

    def setup(self, attr, destval=1.0, duration=1.0, tween=ease_linear):
        self.attr = attr
        self.destval = destval
        self.duration = duration
        self.tween = tween

    def start(self):
        self.startval = getattr(self.target, self.attr)
        self.interval = self.destval - self.startval

    def advance(self, t):
        try:
            value = clamp(
                self.tween(t, self.startval, self.interval, self.duration),
                self.startval,
                self.destval)
        except ZeroDivisionError:
            value = self.destval

        setattr(self.target, self.attr, value)


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

    def update(self, dt):
        if not hasattr(self, '_to_remove'):
            self._to_remove = set([])

        self._actions = getattr(self, '_actions', set([])) - self._to_remove
        del self._to_remove

        for action in self._actions:
            action.update(dt)

            if action.done:
                self.remove_action(action)


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