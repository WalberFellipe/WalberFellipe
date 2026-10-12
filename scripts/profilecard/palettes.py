"""Theme palettes. The g1..g3 stops drive the color-cycling ASCII gradient."""

DARK = {
    "g1": "#00E5FF", "g2": "#FF2BD6", "g3": "#7C4DFF",
    "bg0": "#0B0F19", "bg1": "#111827",
    "panel": "#0E1424", "border": "#22304D",
    "text": "#E2E8F0", "muted": "#5B6B88",
    "label": "#00E5FF", "accent": "#FF2BD6",
    "scanblend": "screen", "scanop": "0.75",
    "invert": False,
    "heat0": "#161E33", "heat1": "#123B5C", "heat2": "#1A6E92", "heat3": "#00B8D4", "heat4": "#FF2BD6",
}

LIGHT = {
    "g1": "#0891B2", "g2": "#C026D3", "g3": "#6D28D9",
    "bg0": "#F8FAFC", "bg1": "#EEF2F7",
    "panel": "#FFFFFF", "border": "#CBD5E1",
    "text": "#1E293B", "muted": "#8A97AB",
    "label": "#0E7490", "accent": "#A21CAF",
    "scanblend": "multiply", "scanop": "0.55",
    "invert": True,   # dark ink on a light page: dark pixels get the dense glyphs
    "heat0": "#E2E8F0", "heat1": "#A5F3FC", "heat2": "#22D3EE", "heat3": "#0891B2", "heat4": "#C026D3",
}
