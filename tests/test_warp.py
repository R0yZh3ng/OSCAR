import unittest

from display import warp


def parse(css):
    return [float(v) for v in css[len("matrix3d("):-1].split(",")]


class HomographyTest(unittest.TestCase):
    def assertPoint(self, got, want):
        self.assertAlmostEqual(got[0], want[0], places=6)
        self.assertAlmostEqual(got[1], want[1], places=6)

    def test_identity(self):
        h = warp.homography(warp.UNIT_CORNERS, warp.UNIT_CORNERS)
        for i in range(3):
            for j in range(3):
                self.assertAlmostEqual(h[i][j], 1.0 if i == j else 0.0)

    def test_pure_scale_and_shift(self):
        dst = [[10, 20], [110, 20], [110, 70], [10, 70]]
        h = warp.homography(warp.UNIT_CORNERS, dst)
        self.assertPoint(warp.apply(h, 0.5, 0.5), (60, 45))

    def test_trapezoid_maps_corners_exactly(self):
        dst = [[0.2, 0.0], [0.8, 0.0], [1.0, 1.0], [0.0, 1.0]]
        h = warp.homography(warp.UNIT_CORNERS, dst)
        for s, d in zip(warp.UNIT_CORNERS, dst):
            self.assertPoint(warp.apply(h, *s), d)
        # the vanishing-edge midpoint stays on the vertical axis, narrower at the top
        self.assertPoint(warp.apply(h, 0.5, 0.0), (0.5, 0.0))

    def test_collinear_corners_rejected(self):
        with self.assertRaises(ValueError):
            warp.homography(warp.UNIT_CORNERS, [[0, 0], [1, 0], [2, 0], [3, 0]])

    def test_needs_four_points(self):
        with self.assertRaises(ValueError):
            warp.homography(warp.UNIT_CORNERS[:3], warp.UNIT_CORNERS[:3])


class Matrix3dTest(unittest.TestCase):
    def test_identity_corners_give_identity_matrix(self):
        vals = parse(warp.matrix3d(warp.UNIT_CORNERS))
        want = [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1]
        for got, w in zip(vals, want):
            self.assertAlmostEqual(got, w, places=9)

    def test_scale_is_in_diagonal_translate_in_last_column(self):
        vals = parse(warp.matrix3d([[0.1, 0.2], [0.6, 0.2], [0.6, 0.7], [0.1, 0.7]], size=(100, 100)))
        self.assertAlmostEqual(vals[0], 0.5)
        self.assertAlmostEqual(vals[5], 0.5)
        self.assertAlmostEqual(vals[12], 10)
        self.assertAlmostEqual(vals[13], 20)

    def test_css_matrix_matches_homography(self):
        corners = [[0.04, 0.02], [0.97, 0.06], [0.96, 0.95], [0.02, 0.91]]
        v = parse(warp.matrix3d(corners, size=(1280, 720)))
        # CSS column-major: x' = (v0 x + v4 y + v12) / (v3 x + v7 y + v15)
        for (ux, uy), (cx, cy) in zip(warp.UNIT_CORNERS, corners):
            x, y = ux * 1280, uy * 720
            w = v[3] * x + v[7] * y + v[15]
            self.assertAlmostEqual((v[0] * x + v[4] * y + v[12]) / w, cx * 1280, places=4)
            self.assertAlmostEqual((v[1] * x + v[5] * y + v[13]) / w, cy * 720, places=4)


class LegacyTest(unittest.TestCase):
    def test_no_rotation_is_unit_rect(self):
        for got, want in zip(warp.legacy_to_corners(), warp.UNIT_CORNERS):
            self.assertAlmostEqual(got[0], want[0])
            self.assertAlmostEqual(got[1], want[1])

    def test_rotate_y_narrows_one_side(self):
        tl, tr, br, bl = warp.legacy_to_corners(rotate_y=30, perspective=1000)
        self.assertLess(tr[0] - tl[0], 1.0)
        # the edge swung away from the viewer is shorter than the edge swung toward it
        self.assertNotAlmostEqual(br[1] - tr[1], bl[1] - tl[1])

    def test_wall_corners_prefers_explicit_corners(self):
        c = [[0, 0], [1, 0], [1, 1], [0, 1]]
        self.assertEqual(warp.wall_corners({"corners": c, "rotateY": 20}), c)

    def test_wall_corners_falls_back_to_legacy(self):
        got = warp.wall_corners({"rotateX": 10, "perspective": 800})
        self.assertEqual(got, warp.legacy_to_corners(10, 0, 800))

    def test_wall_corners_rejects_wrong_count(self):
        with self.assertRaises(ValueError):
            warp.wall_corners({"corners": [[0, 0]]})


if __name__ == "__main__":
    unittest.main()
