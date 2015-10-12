# -*- coding: utf-8 -*-
"""Caching of OpenGL commmands.

OpenGL Display Lists offer a simple way to precompile batches of OpenGL
commands. The drawback is that the commands, once compiled, can't be
modified.

"""

from pyglet.gl import *

__all__ = (
    'flush',
    'precompile',
    'precompile'
)


def precompile(function, *args, **kwargs):
    """Create OpenGL Display List from the OpenGL commands in given function.

    A Display List will precompile the commands and (if possible) store them in
    graphics memory.

    Returns an id which can be used with precompiled() to execute the cached
    commands.

    """
    id = glGenLists(1)
    glNewList(id, GL_COMPILE)
    function(*args, **kwargs)
    glEndList()
    return id


def precompiled(id):
    """Execute the Display List program with the given id."""
    glCallList(id)


def flush(id):
    """Removethe Display List program with the given id from memory."""
    if id is not None:
        glDeleteLists(id, 1)
