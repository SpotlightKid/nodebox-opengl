# -*- coding: utf-8 -*-

from nodebox.graphics import Color, Filter, Shader, vec2, vec4

__all__ = (
    'AlphaKernelFilter',
    'KernelFilter',
    'Outline',
)


_kernel_shader = """\
uniform sampler2D src;
uniform mat3 kernel;
uniform vec2 offset;
uniform vec4 outline_color;

// apply a 3x3 matrix filter kernel to each pixel
void main() {
    vec2 tex_pos = gl_TexCoord[0].st;
    vec4 _col = texture2D(src, tex_pos) * kernel[1][1];

    _col += texture2D(src, tex_pos + vec2(-offset.x, offset.y)) * kernel[0][0];
    _col += texture2D(src, tex_pos + vec2(-offset.x, 0.0)) * kernel[0][1];
    _col += texture2D(src, tex_pos + vec2(-offset.x, -offset.y)) * kernel[0][2];
    _col += texture2D(src, tex_pos + vec2(0.0, offset.y)) * kernel[1][0];
    _col += texture2D(src, tex_pos + vec2(0.0, -offset.y)) * kernel[1][2];
    _col += texture2D(src, tex_pos + vec2(offset.x, offset.y)) * kernel[2][0];
    _col += texture2D(src, tex_pos + vec2(offset.x, 0.0)) * kernel[2][1];
    _col += texture2D(src, tex_pos + vec2(offset.x, -offset.y)) * kernel[2][2];

    gl_FragColor = _col;
}
"""


class KernelFilter(Filter):
    shader = Shader(fragment=_kernel_shader)
    outline_kernel = (
        (1.0, 1.0, 1.0),   # first *column*
        (1.0, -8.0, 1.0),  # second *column*
        (1.0, 1.0, 1.0)    # third *column*
    )

    def __init__(self, color=Color(0.), width=1.0, **kwargs):
        self.texture = None
        self.color = color
        self.width = width

    def push(self):
        self.shader.set("outline_color", vec4(*self.color))
        self.shader.set("kernel", self.outline_kernel)
        self.shader.set("offset", vec2(1. / self.texture.width * self.width,
                                       1. / self.texture.height * self.width))
        self.shader.push()


_alpha_kernel_shader = """\
uniform sampler2D src;
uniform mat3 kernel;
uniform vec2 offset;
uniform vec4 outline_color;

// apply a 3x3 matrix filter kernel to each pixel
void main() {
    vec2 tex_pos = gl_TexCoord[0].st;
    float alpha = texture2D(src, tex_pos).a * kernel[1][1];

    alpha += texture2D(src, tex_pos + vec2(-offset.x, offset.y)).a * kernel[0][0];
    alpha += texture2D(src, tex_pos + vec2(-offset.x, 0.0)).a * kernel[0][1];
    alpha += texture2D(src, tex_pos + vec2(-offset.x, -offset.y)).a * kernel[0][2];
    alpha += texture2D(src, tex_pos + vec2(0.0, offset.y)).a * kernel[1][0];
    alpha += texture2D(src, tex_pos + vec2(0.0, -offset.y)).a * kernel[1][2];
    alpha += texture2D(src, tex_pos + vec2(offset.x, offset.y)).a * kernel[2][0];
    alpha += texture2D(src, tex_pos + vec2(offset.x, 0.0)).a * kernel[2][1];
    alpha += texture2D(src, tex_pos + vec2(offset.x, -offset.y)).a * kernel[2][2];

    gl_FragColor = vec4(outline_color.r, outline_color.g, outline_color.b, alpha);
}
"""


class AlphaKernelFilter(KernelFilter):
    shader = Shader(fragment=_alpha_kernel_shader)


# Source; http://choruscode.blogspot.de/2013/09/draw-beautiful-font-outlines-with.html
_outline_shader = """\
uniform vec4 font_color;
uniform vec4 outline_color;
uniform vec2 offset;
uniform sampler2D src;

void main() {
    vec2 tex_pos = gl_TexCoord[0].st;

    vec4 n = texture2D(src, vec2(tex_pos.x, tex_pos.y - offset.y));
    vec4 e = texture2D(src, vec2(tex_pos.x + offset.x, tex_pos.y));
    vec4 s = texture2D(src, vec2(tex_pos.x, tex_pos.y + offset.y));
    vec4 w = texture2D(src, vec2(tex_pos.x - offset.x, tex_pos.y));

    vec4 tex_color = texture2D(src, tex_pos);
    float new_alpha = tex_color.a;
    new_alpha = mix(new_alpha, 1.0, s.a);
    new_alpha = mix(new_alpha, 1.0, w.a);
    new_alpha = mix(new_alpha, 1.0, n.a);
    new_alpha = mix(new_alpha, 1.0, e.a);

    vec4 outline_color_new = outline_color;
    outline_color_new.a = new_alpha;
    vec4 char_color = tex_color * font_color;

    gl_FragColor = mix(outline_color_new, char_color, char_color.a);
}
"""


class Outline(Filter):
    shader = Shader(fragment=_outline_shader)

    def __init__(self, color=Color(0.), font_color=Color(0.), width=1.):
        self.texture = None
        self.color = color
        self.font_color = font_color
        self.width = width

    def push(self):
        self.shader.set("outline_color", vec4(*self.color))
        self.shader.set("font_color", vec4(*self.font_color))
        self.shader.set("offset", vec2(1. / self.texture.width * self.width,
                                       1. / self.texture.height * self.width))
        self.shader.push()
