# -*- coding: utf-8 -*-
"""Create movie file from a nodebox animation."""

import subprocess as sp

import pyglet


__all__ = ('Movie', 'MovieEncodingError')


class MovieEncodingError(Exception):
    pass


class Movie(object):
    def __init__(self, canvas, filename, compression=0., encoder="ffmpeg"):
        """Create a movie recorder for the given Canvas.

        If fps=None, uses the actual framerate of the canvas. Compression can
        be given as a number between 0.0-1.0. The encoder parameter specifies
        the path to the ffmpeg executable.

        Saving the movie requires ffmpeg (http://www.ffmpeg.org/).

        Raises MovieEncoderError if unable to launch ffmpeg from the shell.

        """
        self._canvas = canvas
        self._bufs = pyglet.image.get_buffer_manager()
        self._compression = compression
        try:
            r = str(int(canvas.fps))
            q = str(int(max(0, min(1, self._compression)) * 30.0 + 1))
            cmdline = [encoder,
                # Option -y overwrites exising files.
                '-y',
                '-f', 'png_pipe',
                '-framerate', r,
                # Params for piping in raw video frames
                # But writing PNGs from pyglet is actually faster
                #'-f', 'rawvideo',
                #'-vcodec', 'rawvideo',
                #'-s', '%dx%d' % (canvas.width, canvas.height),
                #'-pix_fmt', 'rgb24',
                '-i', '-',
                "-r", r,
                "-q:v", q,
                '-an',
                filename]
            self._ffmpeg = sp.Popen(cmdline, stderr=sp.PIPE, stdin=sp.PIPE)
        except Exception, e:
            raise MovieEncodingError

    def record(self):
        """Add the current frame to the movie.

        Call this method at the end of Canvas.draw().

        """
        self._bufs.get_color_buffer().get_image_data().save('frame.png',
            self._ffmpeg.stdin)
        #data = self._bufs.get_color_buffer().get_image_data().get_data(
        #    'RGB', self._canvas.width * 3)
        #self._ffmpeg.stdin.write(data)

    def save(self):
        stdin, stdout = self._ffmpeg.communicate()

        if self._ffmpeg.wait() != 0:
            raise MovieEncodingError(stdout)
