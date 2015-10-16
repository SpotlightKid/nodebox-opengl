# -*- coding: utf-8 -*-
# Textures and quad vertices are cached for performance.
# Textures remain in cache for the duration of the program.
# Quad vertices are cached as Display Lists and destroyed when the Image object
# is deleted.
# For optimal performance, images should be created once (not every frame) and
# its quads left unmodified.
# Performance should be comparable to (moving) pyglet.Sprites drawn in a batch.

from __future__ import absolute_import

import pyglet

from pyglet.gl import *

from .caching import *
from .color import Color
from .state import global_state as _g

__all__ = (
    'Image',
    'ImageError',
    'Pixels',
    'Quad',
    'cache',
    'cached',
    'crop',
    'image',
    'image',
    'imagesize',
    'pixels',
    'texture'
)

_IMAGE_CACHE = 200
_image_cache = {} # Image object referenced by Image.texture.id.
_image_queue = [] # Most recent id's are at the front of the list.
_texture_cache  = {} # pyglet.Texture referenced by filename.
_texture_cached = {} # pyglet.Texture.id is in keys once the image has been cached.

try:
    stringtypes = (str, unicode)
except NameError:
    stringtypes = (str,)


class ImageError(Exception):
    pass


def texture(img, data=None):
    """Return a (cached) texture from the given image filename or byte data.

    When a Image or Pixels object is given, returns the associated texture.

    """
    # Image texture stored in cache, referenced by file path
    # (or a custom id defined with cache()).
    if isinstance(img, stringtypes + (int,)) and img in _texture_cache:
        return _texture_cache[img]

    # Image file path, load it, cache it, return texture.
    if isinstance(img, stringtypes):
        try:
            cache(img, pyglet.image.load(img).get_texture())
        except IOError:
            raise ImageError("can't load image from %s" % repr(img))
        return _texture_cache[img]

    # Image texture, return original.
    if isinstance(img, pyglet.image.Texture):
        return img

    # Image object, return image texture.
    # (if you use this to create a new image, the new image will do expensive
    # caching as well).
    if isinstance(img, Image):
        return img.texture

    # Pixels object, return pixel texture.
    if isinstance(img, Pixels):
        return img.texture

    # Pyglet image data.
    if isinstance(img, pyglet.image.ImageData):
        return img.texture

    # Image data as byte string, load it, return texture.
    if isinstance(data, stringtypes):
        return pyglet.image.load("", file=StringIO(data)).get_texture()

    # Don't know how to handle this image.
    raise ImageError("unknown image type: %s" % repr(img.__class__))


def cache(id, texture):
    """Store the given texture in cache, referenced by id (which can then be
    passed to image()).

    This is useful for procedurally rendered images (which are not stored in
    cache by default).

    """
    if isinstance(texture, (Image, Pixels)):
        texture = texture.texture

    if not isinstance(texture, pyglet.image.Texture):
        raise ValueError("Can only cache texture, not %r" %
                        texture.__class__.__name__)

    _texture_cache[id] = texture
    _texture_cached[_texture_cache[id].id] = id


def cached(texture):
    """Return the cache id if the texture has been cached (None otherwise)."""
    if isinstance(texture, (Image, Pixels)):
        texture = texture.texture

    if isinstance(texture, pyglet.image.Texture):
        return _texture_cached.get(texture.texture.id)

    if isinstance(texture, stringtypes + (int,)):
        return texture in _texture_cache and texture or None

    return None


def _render(texture, quad=None):
    """Render the texture on the canvas inside a quadtriliteral (rectangle).

    The quadriliteral can be distorted by giving corner offset coordinates.

    """
    t = texture.tex_coords # power-2 dimensions
    w = texture.width      # See Pyglet programming guide -> OpenGL imaging.
    h = texture.height
    dx1, dy1, dx2, dy2, dx3, dy3, dx4, dy4 = quad or (0, 0, 0, 0, 0, 0, 0, 0)
    glEnable(texture.target)
    glBindTexture(texture.target, texture.id)
    glBegin(GL_QUADS)
    glTexCoord3f(t[0], t[1], t[2] )
    glVertex3f(dx4, dy4, 0)
    glTexCoord3f(t[3], t[4], t[5] )
    glVertex3f(dx3 + w, dy3, 0)
    glTexCoord3f(t[6], t[7], t[8] )
    glVertex3f(dx2 + w, dy2 + h, 0)
    glTexCoord3f(t[9], t[10], t[11])
    glVertex3f(dx1, dy1 + h, 0)
    glEnd()
    glDisable(texture.target)


class Quad(list):
    """Describes the four-sided polygon on which an image texture is "mounted".

    This is a quadrilateral (four sides) of which the vertices do not
    necessarily have a straight angle (i.e. the corners can be distorted).

    """
    def __init__(self, dx1=0, dy1=0, dx2=0, dy2=0, dx3=0, dy3=0, dx4=0, dy4=0):
        """Create quad from given four corners given as eight coordinates."""
        list.__init__(self, (dx1, dy1, dx2, dy2, dx3, dy3, dx4, dy4))
        # Image objects poll Quad._dirty to check if the image cache is outdated.
        self._dirty = True

    def copy(self):
        return Quad(*self)

    def reset(self):
        list.__init__(self, (0,0,0,0,0,0,0,0))
        self._dirty = True

    def __setitem__(self, i, v):
        list.__setitem__(self, i, v)
        self._dirty = True

    def _get_dx1(self): return self[0]
    def _get_dy1(self): return self[1]
    def _get_dx2(self): return self[2]
    def _get_dy2(self): return self[3]
    def _get_dx3(self): return self[4]
    def _get_dy3(self): return self[5]
    def _get_dx4(self): return self[6]
    def _get_dy4(self): return self[7]

    def _set_dx1(self, v): self[0] = v
    def _set_dy1(self, v): self[1] = v
    def _set_dx2(self, v): self[2] = v
    def _set_dy2(self, v): self[3] = v
    def _set_dx3(self, v): self[4] = v
    def _set_dy3(self, v): self[5] = v
    def _set_dx4(self, v): self[6] = v
    def _set_dy4(self, v): self[7] = v

    dx1 = property(_get_dx1, _set_dx1)
    dy1 = property(_get_dy1, _set_dy1)
    dx2 = property(_get_dx2, _set_dx2)
    dy2 = property(_get_dy2, _set_dy2)
    dx3 = property(_get_dx3, _set_dx3)
    dy3 = property(_get_dy3, _set_dy3)
    dx4 = property(_get_dx4, _set_dx4)
    dy4 = property(_get_dy4, _set_dy4)


class Image(object):
    """A texture that can be drawn at a given position.

    The quadrilateral in which the texture is drawn can be distorted (slow,
    image cache is flushed). The image can be resized, colorized and its
    opacity can be set.

    """
    def __init__(self, path, x=0, y=0, width=None, height=None, alpha=1.0,
                 data=None):
        """Create image from file at given path or data."""
        self._src = (path, data)
        self._texture = texture(path, data=data)
        self._cache = None
        self.x = x
        self.y = y
        # Scaled width, Image.texture.width yields original width.
        self.width = width or self._texture.width
        # Scaled height, Image.texture.height yields original height.
        self.height = height or self._texture.height
        self.quad = Quad()
        self.color = Color(1.0, 1.0, 1.0, alpha)

    def copy(self, texture=None, width=None, height=None):
        img = (self.__class__(self._src[0], data=self._src[1])
               if texture is None else self.__class__(texture))
        img.x = self.x
        img.y = self.y
        img.width  = self.width
        img.height = self.height
        img.quad = self.quad.copy()
        img.color = self.color.copy()

        if width is not None:
            img.width = width

        if height is not None:
            img.height = height

        return img

    @property
    def id(self):
        return self._texture.id

    @property
    def texture(self):
        return self._texture

    @property
    def xy(self):
        return (self.x, self.y)

    @xy.setter
    def xy(self, v):
        self.x = v[0]
        self.y = v[1]

    @property
    def size(self):
        return (self.width, self.height)

    @size.setter
    def size(self, wh):
        self.width  = wh[0]
        self.height = wh[1]

    @property
    def alpha(self):
        return self.color[3]

    @alpha.setter
    def alpha(self, v):
        self.color[3] = v

    def distort(self, dx1=0, dy1=0, dx2=0, dy2=0, dx3=0, dy3=0, dx4=0, dy4=0):
        """Adjust the four-sided polygon on which an image texture is mounted.

        This is done by incrementing the corner coordinates with the given
        values.

        """
        for i, v in enumerate((dx1, dy1, dx2, dy2, dx3, dy3, dx4, dy4)):
            if v != 0:
                self.quad[i] += v

    def adjust(r=1.0, g=1.0, b=1.0, a=1.0):
        """Adjust image color by multiplying RGBA channels with given values.
        """
        self.color[0] *= r
        self.color[1] *= g
        self.color[2] *= b
        self.color[3] *= a

    def draw(self, x=None, y=None, width=None, height=None, alpha=None,
             color=None, filter=None):
        """Draw the image.

        The given parameters (if any) override the image's attributes.

        """
        # Calculate and cache the quad vertices as a Display List.
        # If the quad has changed, update the cache.
        if self._cache is None or self.quad._dirty:
            flush(self._cache)
            self._cache = precompile(_render, self._texture, self.quad)
            self.quad._dirty = False

        # Given parameters override Image attributes.
        if x is None:
            x = self.x

        if y is None:
            y = self.y

        if width is None:
            width = self.width

        if height is None:
            height = self.height

        if color and len(color) < 4:
            color = color[0], color[1], color[2], 1.0

        if color is None:
            color = self.color

        if alpha is not None:
            color = color[0], color[1], color[2], alpha

        if filter:
            # Register the current texture with the filter.
            filter.texture = self._texture
            filter.push()

        # Round position (x,y) to nearest integer to avoid sub-pixel rendering.
        # This ensures there are no visual artefacts on transparent borders
        # (e.g. the "white halo").
        # Halo can also be avoided by overpainting in the source image, but
        # this requires some work:
        # http://technology.blurst.com/remove-white-borders-in-transparent-textures/
        x = round(x)
        y = round(y)
        w = float(width) / self._texture.width
        h = float(height) / self._texture.height
        # Transform and draw the quads.
        glPushMatrix()
        glTranslatef(x, y, 0)
        glScalef(w, h, 0)
        glColor4f(color[0], color[1], color[2], color[3] * _g.alpha)
        glCallList(self._cache)
        glPopMatrix()

        if filter:
            filter.pop()

    def save(self, path):
        """Exports the image as a PNG-file."""
        self._texture.save(path)

    def __repr__(self):
        return "%s(x=%.1f, y=%.1f, width=%.1f, height=%.1f, alpha=%.2f)" % (
            self.__class__.__name__, self.x, self.y, self.width, self.height,
            self.alpha)

    def __del__(self):
        try:
            if hasattr(self, "_cache") and self._cache is not None and flush:
                flush(self._cache)
        except:
            pass


def image(img, x=None, y=None, width=None, height=None,
          alpha=None, color=None, filter=None, data=None, draw=True):
    """Draws the image at (x,y), scaling it to the given width and height.

    The image's transparency can be set with alpha (0.0-1.0).

    Applies the given color adjustment, quad distortion and filter (one filter
    can be specified).

    Note: with a filter enabled, alpha and color will not be applied. This is
    because the filter overrides the default drawing behavior with its own.

    """
    if not isinstance(img, Image):
        # If the given image is not an Image object, create one on the fly.
        # This object is cached for reuse.
        # The cache has a limited size (200), so the oldest Image objects are
        # deleted.
        t = texture(img, data=data)

        if t.id in _image_cache:
            img = _image_cache[t.id]
        else:
            img = Image(img, data=data)
            _image_cache[img.texture.id] = img
            _image_queue.insert(0, img.texture.id)

            for id in reversed(_image_queue[_IMAGE_CACHE:]):
                del _image_cache[id]
                del _image_queue[-1]

    # Draw the image.
    if draw:
        img.draw(x, y, width, height, alpha, color, filter)

    return img


def imagesize(img):
    """Returns a (width, height)-tuple with the image dimensions."""
    t = texture(img)
    return (t.width, t.height)


def crop(img, x=0, y=0, width=None, height=None):
    """Returns the given (x, y, width, height)-region from the image.

    Use this to pass cropped image files to image().

    """
    t = texture(img)

    if width  is None:
        width  = t.width

    if height is None:
        height = t.height

    t = t.get_region(x, y, min(t.width-x, width), min(t.height-y, height))

    if isinstance(img, Image):
        img = img.copy(texture=t)
        return img.copy(texture=t, width=t.width, height=t.height)

    if isinstance(img, Pixels):
        return Pixels(t)

    if isinstance(img, pyglet.image.Texture):
        return t

    return Image(t)


#--- PIXELS -------------------------------------------------------------------

class Pixels(list):

    def __init__(self, img):
        """A list of RGBA color values (0-255) for each pixel in given image.

        The Pixels object can be passed to the image() command.

        """
        self._img  = texture(img).get_image_data()
        # A negative pitch means the pixels are stored top-to-bottom row.
        self._flipped = self._img.pitch >= 0
        # Data yields a byte array if no conversion (e.g. BGRA => RGBA) was necessary,
        # or a byte string otherwise - which needs to be converted to a list of ints.
        data = self._img.get_data("RGBA",
                                  self._img.width * 4 * (-1, 1)[self._flipped])
        if isinstance(data, str):
            data = [ord(x) for x in list(data)]

        # Some formats seem to store values from -1 to -256.
        data = [(256 + v) % 256 for v in data]
        self.array = data
        self._texture  = None

    @property
    def width(self):
        return self._img.width

    @property
    def height(self):
        return self._img.height

    @property
    def size(self):
        return (self.width, self.height)

    def __len__(self):
        return len(self.array) / 4

    def __iter__(self):
        for i in range(len(self)):
            yield self[i]

    def __getitem__(self, i):
        """Returns a list of RGBA channel values between 0-255 from pixel i.

        Users need to wrap the list in a Color themselves for performance.

        - r,g,b,a = Pixels[i]
        - clr = Color(Pixels[i], base=255)

        """
        return self.array[i*4:i*4+4]

    def __setitem__(self, i, v):
        """Sets pixel i to the given RGBA values.

        Users need to unpack a Color themselves for performance, and are
        resposible for keeping channes values between 0 and 255 (otherwise an
        error will occur when Pixels.update() is called),

        - Pixels[i] = r,g,b,a
        - Pixels[i] = clr.map(base=255)

        """
        for j in range(4):
            self.array[i*4+j] = v[j]

    def __getslice__(self, i, j):
        return [self[i+n] for n in range(j-i)]

    def __setslice__(self, i, j, seq):
        for n in range(j-i):
            self[i+n] = seq[n]

    def map(self, function):
        """Applies a function to each pixel.

        Function takes a list of R,G,B,A channel values and must return a
        similar list.

        """
        for i in range(len(self)):
            self[i] = function(self[i])

    def get(self, i, j):
        """Returns the pixel at row i, column j as a Color object."""
        if 0 <= i < self.width and 0 <= j < self.height:
            return Color(self[i + j * self.width], base=255)

    def set(self, i, j, clr):
        """Sets the pixel at row i, column j from a Color object."""
        if 0 <= i < self.width and 0 <= j < self.height:
            self[i + j * self.width] = clr.map(base=255)

    def update(self):
        """Pixels.update() must be called to refresh the image."""
        data = self.array
        data = "".join(map(chr, data))
        self._img.set_data("RGBA", self._img.width*4*(-1,1)[self._flipped], data)
        self._texture = self._img.get_texture()

    @property
    def texture(self):
        if self._texture is None:
            self.update()
        return self._texture

    def copy(self):
        return Pixels(self.texture)

    def __repr__(self):
        return "%s(width=%.1f, height=%.1f)" % (
            self.__class__.__name__, self.width, self.height)


pixels = Pixels
