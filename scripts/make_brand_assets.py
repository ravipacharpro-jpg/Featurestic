#!/usr/bin/env python3
"""
Builds Featurestic's launcher icon and splash assets from one image.

Usage:
    python3 scripts/make_brand_assets.py                  # placeholder monogram
    python3 scripts/make_brand_assets.py logo.jpg         # your own logo
    python3 scripts/make_brand_assets.py --default        # scripts/brand/logo.jpg

What it does with an image:
  * finds the artwork inside the picture (ignores the plain background),
  * re-centres it and scales it so it survives Android's adaptive-icon mask,
  * paints the leftover space with the picture's own background colour, so the
    icon and the splash screen blend without a visible square.

Outputs (all overwritten):
  drawable-nodpi/ic_launcher_foreground.png
  drawable-nodpi/splash_logo.png
  drawable-nodpi/splash_wordmark.png
  drawable/ic_launcher_background.xml      (solid brand colour)
  drawable/splash_background.xml           (brand colour + logo + wordmark)
  mipmap-*/ic_launcher[_round].png         (Android 7 and older)
  values/themes.xml, values/splash_colors.xml
"""
import os
import sys

from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RES = os.path.join(ROOT, "app", "src", "main", "res")
DEFAULT_LOGO = os.path.join(ROOT, "scripts", "brand", "logo.jpg")

NAME = "FEATURESTIC"
FALLBACK_BG = (17, 18, 23)       # graphite, the app's own background
ACCENT = (94, 234, 212)          # teal, only used by the placeholder
WHITE = (245, 246, 250)

# how much of the canvas the artwork should fill
ADAPTIVE_CONTENT = 0.62          # stays inside the 66% adaptive-icon safe zone
SPLASH_CONTENT = 0.70
LEGACY_CONTENT = 0.74

FONT_CANDIDATES = [
    "/system/fonts/RobotoStatic-Regular.ttf",
    "/system/fonts/Roboto-Regular.ttf",
    "/system/fonts/DroidSans-Bold.ttf",
    os.path.join(os.environ.get("PREFIX", "/data/data/com.termux/files/usr"),
                 "share", "fonts", "TTF", "DejaVuSans-Bold.ttf"),
]


# --------------------------------------------------------------------------- helpers

def font(size: int):
    for path in FONT_CANDIDATES:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except OSError:
                pass
    return ImageFont.load_default()


def rounded_mask(size: int, radius: int) -> Image.Image:
    m = Image.new("L", (size, size), 0)
    ImageDraw.Draw(m).rounded_rectangle((0, 0, size - 1, size - 1), radius=radius, fill=255)
    return m


def circle_mask(size: int) -> Image.Image:
    m = Image.new("L", (size, size), 0)
    ImageDraw.Draw(m).ellipse((0, 0, size - 1, size - 1), fill=255)
    return m


def background_colour(im: Image.Image):
    """The colour of the picture's border, i.e. what the artwork sits on."""
    rgb = im.convert("RGB")
    w, h = rgb.size
    px = rgb.load()
    samples = []
    for i in range(0, 100, 2):
        x = min(w - 1, i * w // 100)
        y = min(h - 1, i * h // 100)
        samples += [px[x, 0], px[x, h - 1], px[0, y], px[w - 1, y]]
    samples.sort(key=lambda c: c[0] + c[1] + c[2])
    return samples[len(samples) // 2]


def content_bbox(im: Image.Image, threshold: int = 48):
    """Bounding box of the bright artwork, ignoring the background."""
    small = im.convert("RGB").resize((160, 160), Image.BILINEAR)
    px = small.load()
    bg = background_colour(im)
    bg_lum = max(bg)
    cut = max(threshold, bg_lum + 24)
    minx, miny, maxx, maxy = 160, 160, -1, -1
    for y in range(160):
        for x in range(160):
            r, g, b = px[x, y]
            if max(r, g, b) > cut:
                minx, miny = min(minx, x), min(miny, y)
                maxx, maxy = max(maxx, x), max(maxy, y)
    if maxx < 0:
        return (0, 0, im.width, im.height)
    scale_x, scale_y = im.width / 160, im.height / 160
    return (int(minx * scale_x), int(miny * scale_y),
            int((maxx + 1) * scale_x), int((maxy + 1) * scale_y))


def centred_square(im: Image.Image, content_fraction: float) -> Image.Image:
    """Re-frames the picture so the artwork fills `content_fraction` of a square."""
    rgb = im.convert("RGB")
    x0, y0, x1, y1 = content_bbox(rgb)
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    side = max(x1 - x0, y1 - y0) / content_fraction
    side = int(round(side))
    left, top = int(round(cx - side / 2)), int(round(cy - side / 2))

    out = Image.new("RGB", (side, side), background_colour(rgb))
    sx0, sy0 = max(0, left), max(0, top)
    sx1, sy1 = min(rgb.width, left + side), min(rgb.height, top + side)
    if sx1 > sx0 and sy1 > sy0:
        out.paste(rgb.crop((sx0, sy0, sx1, sy1)), (sx0 - left, sy0 - top))
    return out


def has_alpha(im: Image.Image) -> bool:
    if im.mode not in ("RGBA", "LA"):
        return False
    return im.getchannel("A").getextrema()[0] < 250


def placeholder_mark(size: int) -> Image.Image:
    """A graphite tile with a white F — only used until a real logo is given."""
    im = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    pad = size * 0.10
    d.rounded_rectangle((pad, pad, size - pad, size - pad), radius=size * 0.22,
                        fill=(*FALLBACK_BG, 255))
    glow = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    ImageDraw.Draw(glow).ellipse((size * 0.18, size * 0.18, size * 0.82, size * 0.82),
                                 fill=(*ACCENT, 40))
    im.alpha_composite(glow.filter(ImageFilter.GaussianBlur(size * 0.05)))
    f = font(int(size * 0.56))
    box = d.textbbox((0, 0), "F", font=f)
    w, h = box[2] - box[0], box[3] - box[1]
    d.text(((size - w) / 2 - box[0], (size - h) / 2 - box[1] - size * 0.01),
           "F", font=f, fill=(*WHITE, 255))
    d.ellipse((size * 0.70, size * 0.66, size * 0.78, size * 0.74), fill=(*ACCENT, 255))
    return im


def wordmark() -> Image.Image:
    """200x80dp at 4x, the size Android reserves for the splash branding image."""
    w, h = 800, 320
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    f = font(92)
    gap = 18
    widths = [d.textlength(ch, font=f) for ch in NAME]
    total = sum(widths) + gap * (len(NAME) - 1)
    x = (w - total) / 2
    for ch, cw in zip(NAME, widths):
        d.text((x, (h - 112) / 2), ch, font=f, fill=(*WHITE, 215), stroke_width=1,
               stroke_fill=(*WHITE, 215))
        x += cw + gap
    return im


# --------------------------------------------------------------------------- writers

def write_icon_background(colour):
    path = os.path.join(RES, "drawable", "ic_launcher_background.xml")
    with open(path, "w", encoding="utf-8") as f:
        f.write(
            '<?xml version="1.0" encoding="utf-8"?>\n'
            '<vector xmlns:android="http://schemas.android.com/apk/res/android"\n'
            '    android:width="108dp" android:height="108dp"\n'
            '    android:viewportWidth="108" android:viewportHeight="108">\n'
            f'    <path android:fillColor="#FF{colour[0]:02X}{colour[1]:02X}{colour[2]:02X}" '
            'android:pathData="M0,0h108v108h-108z" />\n'
            '</vector>\n'
        )


def write_splash_background():
    path = os.path.join(RES, "drawable", "splash_background.xml")
    with open(path, "w", encoding="utf-8") as f:
        f.write(
            '<?xml version="1.0" encoding="utf-8"?>\n'
            '<layer-list xmlns:android="http://schemas.android.com/apk/res/android">\n'
            '    <!-- Brand splash: solid colour, centred logo, wordmark at the bottom -->\n'
            '    <item android:drawable="@color/splash_bg" />\n'
            '    <item android:gravity="center" android:width="288dp" android:height="288dp"\n'
            '        android:drawable="@drawable/splash_logo" />\n'
            '    <item android:gravity="bottom|center_horizontal" android:width="200dp" android:height="80dp"\n'
            '        android:bottom="60dp" android:drawable="@drawable/splash_wordmark" />\n'
            '</layer-list>\n'
        )


def write_splash_colour(colour):
    path = os.path.join(RES, "values", "splash_colors.xml")
    with open(path, "w", encoding="utf-8") as f:
        f.write(
            '<?xml version="1.0" encoding="utf-8"?>\n'
            '<resources>\n'
            '    <!-- Startup splash and window background before the app theme loads: the logo\'s own\n'
            '         background colour, so the tap-to-open zoom flows straight into the splash. -->\n'
            f'    <color name="splash_bg">#FF{colour[0]:02X}{colour[1]:02X}{colour[2]:02X}</color>\n'
            '    <bool name="splash_light_bars">false</bool>\n'
            '</resources>\n'
        )


def patch_themes():
    path = os.path.join(RES, "values", "themes.xml")
    with open(path, "r", encoding="utf-8") as f:
        s = f.read()
    s = s.replace("@drawable/splash_prism_animated", "@drawable/splash_logo")
    s = s.replace("splash with the centered Prism mark on graphite",
                  "splash with the centered Featurestic logo")
    with open(path, "w", encoding="utf-8") as f:
        f.write(s)


# --------------------------------------------------------------------------- main

def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if args:
        src = args[0]
    elif os.path.exists(DEFAULT_LOGO):
        src = DEFAULT_LOGO
    else:
        src = None
    if src and not os.path.exists(src):
        sys.exit(f"no such file: {src}")

    nodpi = os.path.join(RES, "drawable-nodpi")
    os.makedirs(nodpi, exist_ok=True)

    if not src:
        mark = placeholder_mark(432)
        colour = FALLBACK_BG
        # transparent placeholder: keep the solid background layer behind it
        mark.save(os.path.join(nodpi, "ic_launcher_foreground.png"))
        mark.resize((432, 432), Image.LANCZOS).save(os.path.join(nodpi, "splash_logo.png"))
        mode = "placeholder monogram"
        transparent = True
    else:
        im = Image.open(src)
        transparent = has_alpha(im)
        if transparent:
            # a cut-out PNG: keep it transparent, let the colour layer show through
            rgba = im.convert("RGBA")
            colour = FALLBACK_BG
            for target, frac in ((os.path.join(nodpi, "ic_launcher_foreground.png"), ADAPTIVE_CONTENT),
                                 (os.path.join(nodpi, "splash_logo.png"), SPLASH_CONTENT)):
                m = rgba.copy()
                m.thumbnail((int(432 * frac), int(432 * frac)), Image.LANCZOS)
                canvas = Image.new("RGBA", (432, 432), (0, 0, 0, 0))
                canvas.alpha_composite(m, ((432 - m.width) // 2, (432 - m.height) // 2))
                canvas.save(target)
            mode = "transparent mark"
        else:
            colour = background_colour(im)
            centred_square(im, ADAPTIVE_CONTENT).resize((432, 432), Image.LANCZOS) \
                .save(os.path.join(nodpi, "ic_launcher_foreground.png"))
            centred_square(im, SPLASH_CONTENT).resize((432, 432), Image.LANCZOS) \
                .save(os.path.join(nodpi, "splash_logo.png"))
            mode = "full-bleed picture"

    wordmark().save(os.path.join(nodpi, "splash_wordmark.png"))

    # the icon shown at the top of the GitHub README
    readme_dir = os.path.join(ROOT, "docs", "readme")
    if os.path.isdir(readme_dir):
        Image.open(os.path.join(nodpi, "ic_launcher_foreground.png")) \
            .convert("RGB").resize((256, 256), Image.LANCZOS) \
            .save(os.path.join(readme_dir, "featurestic.png"))

    write_icon_background(colour)
    write_splash_background()
    write_splash_colour(colour)
    patch_themes()

    # the old vectors are replaced by the PNGs above (same resource names)
    for stale in ("drawable/ic_launcher_foreground.xml",
                  "drawable/splash_prism_animated.xml",
                  "drawable/splash_wordmark.xml"):
        p = os.path.join(RES, stale)
        if os.path.exists(p):
            os.remove(p)

    for density, px in (("mdpi", 48), ("hdpi", 72), ("xhdpi", 96),
                        ("xxhdpi", 144), ("xxxhdpi", 192)):
        d = os.path.join(RES, f"mipmap-{density}")
        os.makedirs(d, exist_ok=True)
        for round_icon in (False, True):
            if src and not transparent:
                base = centred_square(Image.open(src), LEGACY_CONTENT).resize((px, px), Image.LANCZOS)
                base = base.convert("RGBA")
            elif src:
                base = Image.new("RGBA", (px, px), (*colour, 255))
                m = Image.open(src).convert("RGBA")
                m.thumbnail((int(px * LEGACY_CONTENT),) * 2, Image.LANCZOS)
                base.alpha_composite(m, ((px - m.width) // 2, (px - m.height) // 2))
            else:
                base = placeholder_mark(px).resize((px, px), Image.LANCZOS)
                base = base.convert("RGBA")
                tile = Image.new("RGBA", (px, px), (*colour, 255))
                tile.alpha_composite(base)
                base = tile
            mask = circle_mask(px) if round_icon else rounded_mask(px, int(px * 0.22))
            base.putalpha(mask)
            name = "ic_launcher_round.png" if round_icon else "ic_launcher.png"
            base.save(os.path.join(d, name))

    print(f"✓ brand assets written (source: {src or 'placeholder monogram'}, mode: {mode})")


if __name__ == "__main__":
    main()
