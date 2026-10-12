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


def portrait_ascii(path, cols=100, crop=(0.06, 0.0, 0.94, 0.84), ramp=RAMP):
    """Rows of ASCII art, right-stripped, each at most `cols` wide."""
    img = Image.open(path).convert("RGB")
    mask = subject_mask(img)
    w, h = img.size
    box = (int(crop[0] * w), int(crop[1] * h), int(crop[2] * w), int(crop[3] * h))
    img, mask = img.crop(box), mask.crop(box)
    w, h = img.size

    gray = ImageOps.autocontrast(ImageOps.grayscale(img), cutoff=1)
    gray = ImageEnhance.Contrast(gray).enhance(1.25)

    rows = int(cols * (h / w) * ADVANCE)
    gray = gray.resize((cols, rows), Image.LANCZOS)
    mask = mask.resize((cols, rows), Image.LANCZOS)

    top = len(ramp) - 2
    lines = []
    for y in range(rows):
        line = []
        for x in range(cols):
            if mask.getpixel((x, y)) < 128:
                line.append(" ")
            else:
                line.append(ramp[1 + int(gray.getpixel((x, y)) / 255 * top)])
        lines.append("".join(line).rstrip())
    return lines
