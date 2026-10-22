"""Corner-pinning math for per-wall projection warp (see docs/PROJECTION_PLAN.md).

A wall's warp is four normalized corners (TL, TR, BR, BL) of the projector output where the page
should land. `matrix3d` turns them into the CSS transform applied to the /stage wrapper. Pure
Python, no browser or hardware; display/static/warp.js mirrors `homography` and `matrix3d`.
"""

import math

# Matches the 16:9 projector output; only matters for converting legacy rotate/perspective keys
DEFAULT_SIZE = (1280, 720)
UNIT_CORNERS = [[0, 0], [1, 0], [1, 1], [0, 1]]


def homography(src, dst):
    """3x3 matrix H (row-major, H[2][2] == 1) mapping each src point onto its dst point.

    Standard 4-point DLT: eight equations, eight unknowns, solved by Gaussian elimination.
    """
    if len(src) != 4 or len(dst) != 4:
        raise ValueError("need exactly 4 source and 4 destination points")
    rows = []
    for (x, y), (u, v) in zip(src, dst):
        rows.append([x, y, 1, 0, 0, 0, -u * x, -u * y, u])
        rows.append([0, 0, 0, x, y, 1, -v * x, -v * y, v])
    for col in range(8):
        pivot = max(range(col, 8), key=lambda r: abs(rows[r][col]))
        if abs(rows[pivot][col]) < 1e-12:
            raise ValueError("degenerate corners (three or more are collinear)")
        rows[col], rows[pivot] = rows[pivot], rows[col]
        for r in range(8):
            if r != col:
                f = rows[r][col] / rows[col][col]
                rows[r] = [a - f * b for a, b in zip(rows[r], rows[col])]
    h = [rows[i][8] / rows[i][i] for i in range(8)]
    return [h[0:3], h[3:6], h[6:8] + [1.0]]


def apply(h, x, y):
    """Map one point through homography h."""
    w = h[2][0] * x + h[2][1] * y + h[2][2]
    return ((h[0][0] * x + h[0][1] * y + h[0][2]) / w,
            (h[1][0] * x + h[1][1] * y + h[1][2]) / w)


def matrix3d(corners, size=DEFAULT_SIZE):
    """CSS `matrix3d(...)` that pins a size-pixel element's corners onto the normalized corners.

    Use with `transform-origin: 0 0`. Column-major, z left untouched.
    """
    w, h = size
    src = [[x * w, y * h] for x, y in UNIT_CORNERS]
    dst = [[x * w, y * h] for x, y in corners]
    (a, b, c), (d, e, f), (g, hh, _) = homography(src, dst)
    vals = [a, d, 0, g, b, e, 0, hh, 0, 0, 1, 0, c, f, 0, 1]
    return "matrix3d(" + ", ".join(f"{v:.10g}" for v in vals) + ")"


def legacy_to_corners(rotate_x=0, rotate_y=0, perspective=1000, size=DEFAULT_SIZE):
    """Normalized corners for the old `perspective(p) rotateX(a) rotateY(b)` CSS-class warp.

    Rotation is about the element's center, angles in degrees, same order CSS applies them
    (rotateY first, then rotateX, then perspective).
    """
    w, h = size
    ax, ay = math.radians(rotate_x), math.radians(rotate_y)
    out = []
    for ux, uy in UNIT_CORNERS:
        x, y, z = (ux - 0.5) * w, (uy - 0.5) * h, 0.0
        x, z = x * math.cos(ay) + z * math.sin(ay), -x * math.sin(ay) + z * math.cos(ay)
        y, z = y * math.cos(ax) - z * math.sin(ax), y * math.sin(ax) + z * math.cos(ax)
        s = perspective / (perspective - z)
        out.append([(x * s) / w + 0.5, (y * s) / h + 0.5])
    return out


def wall_corners(warp, size=DEFAULT_SIZE):
    """Corners for a presets.json `warp` block: `corners` if present, else converted legacy keys."""
    if warp.get("corners"):
        if len(warp["corners"]) != 4:
            raise ValueError("warp.corners needs exactly 4 points")
        return warp["corners"]
    return legacy_to_corners(warp.get("rotateX", 0), warp.get("rotateY", 0),
                             warp.get("perspective", 1000), size)
