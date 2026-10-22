// Mirror of display/warp.py: 4-point homography -> CSS matrix3d.
const UNIT_CORNERS = [[0, 0], [1, 0], [1, 1], [0, 1]];

function homography(src, dst) {
  const rows = [];
  for (let i = 0; i < 4; i++) {
    const [x, y] = src[i], [u, v] = dst[i];
    rows.push([x, y, 1, 0, 0, 0, -u * x, -u * y, u]);
    rows.push([0, 0, 0, x, y, 1, -v * x, -v * y, v]);
  }
  for (let col = 0; col < 8; col++) {
    let pivot = col;
    for (let r = col + 1; r < 8; r++) if (Math.abs(rows[r][col]) > Math.abs(rows[pivot][col])) pivot = r;
    if (Math.abs(rows[pivot][col]) < 1e-12) throw new Error("degenerate corners");
    [rows[col], rows[pivot]] = [rows[pivot], rows[col]];
    for (let r = 0; r < 8; r++) {
      if (r === col) continue;
      const f = rows[r][col] / rows[col][col];
      rows[r] = rows[r].map((a, k) => a - f * rows[col][k]);
    }
  }
  const h = rows.map((row, i) => row[8] / row[i]);
  return [h.slice(0, 3), h.slice(3, 6), [h[6], h[7], 1]];
}

// corners are normalized 0..1 (TL, TR, BR, BL); w, h is the element size in px
function matrix3d(corners, w, h) {
  const src = UNIT_CORNERS.map(([x, y]) => [x * w, y * h]);
  const dst = corners.map(([x, y]) => [x * w, y * h]);
  const [[a, b, c], [d, e, f], [g, hh]] = homography(src, dst);
  return "matrix3d(" + [a, d, 0, g, b, e, 0, hh, 0, 0, 1, 0, c, f, 0, 1].join(", ") + ")";
}
