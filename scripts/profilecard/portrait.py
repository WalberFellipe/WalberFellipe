"""Photo -> ASCII portrait, for photos shot against a light, plain background."""
from collections import deque

from PIL import Image, ImageEnhance, ImageFilter, ImageOps

# density ramp, sparse -> dense; index 0 is reserved for the background
RAMP = " .'`:-~=+*cvxzsoaekw%8B#@"

# monospace glyph advance relative to font size; line height == font size
ADVANCE = 0.60


def _is_backdrop(rgb):
    r, g, b = rgb
    luma = 0.299 * r + 0.587 * g + 0.114 * b
    return luma > 150 and max(rgb) - min(rgb) < 40


def subject_mask(img):
    """255 where the person is, 0 for the light backdrop reachable from the border."""
    rgb = img.convert("RGB")
    w, h = rgb.size
    px = rgb.load()
    seen = bytearray(w * h)
    queue = deque()
    for x in range(w):
        queue.append((x, 0))
        queue.append((x, h - 1))
    for y in range(h):
        queue.append((0, y))
        queue.append((w - 1, y))
    while queue:
        x, y = queue.popleft()
        i = y * w + x
        if seen[i] or not _is_backdrop(px[x, y]):
            continue
        seen[i] = 1
        for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if 0 <= nx < w and 0 <= ny < h and not seen[ny * w + nx]:
                queue.append((nx, ny))
    mask = Image.new("L", (w, h))
    mask.putdata([0 if s else 255 for s in seen])
    return mask.filter(ImageFilter.MedianFilter(5))


def _noise(x, y):
    """Deterministic per-cell value in [0, 1) — same portrait on every rebuild."""
    return ((x * 73856093 ^ y * 19349663) % 1000) / 1000


def portrait_ascii(path, cols=104, crop=(0.12, 0.0, 0.88, 0.80), ramp=RAMP,
                   sharpen=140, gamma=1.2, fade=0.25, invert=False):
    """Rows of ASCII art, right-stripped, each at most `cols` wide.

    The bottom `fade` fraction of rows dissolves into noise so the shoulders
    melt away instead of ending in a hard edge. `invert` maps dark pixels to dense
    glyphs, for drawing dark ink on a light background.
    """
    img = Image.open(path).convert("RGB")
    mask = subject_mask(img)
    w, h = img.size
    box = (int(crop[0] * w), int(crop[1] * h), int(crop[2] * w), int(crop[3] * h))
    img, mask = img.crop(box), mask.crop(box)
    w, h = img.size

    gray = ImageOps.autocontrast(ImageOps.grayscale(img), cutoff=1)
    gray = gray.filter(ImageFilter.UnsharpMask(radius=2, percent=sharpen, threshold=2))
    gray = ImageEnhance.Contrast(gray).enhance(1.25)
    if invert:
        gray = ImageOps.invert(gray)

    rows = int(cols * (h / w) * ADVANCE)
    gray = gray.resize((cols, rows), Image.LANCZOS)
    mask = mask.resize((cols, rows), Image.LANCZOS)

    top = len(ramp) - 2
    fade_from = int(rows * (1 - fade))
    lines = []
    for y in range(rows):
        keep = 1.0 if y < fade_from else 1 - (y - fade_from + 1) / (rows - fade_from + 1)
        line = []
        for x in range(cols):
            if mask.getpixel((x, y)) < 128 or _noise(x, y) >= keep:
                line.append(" ")
            else:
                v = (gray.getpixel((x, y)) / 255) ** gamma
                line.append(ramp[1 + int(v * top)])
        lines.append("".join(line).rstrip())
    return lines
