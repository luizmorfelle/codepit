import unittest
from widgets import pet


class TestPet(unittest.TestCase):
    def test_frame_for_no_blink_returns_base_mood(self):
        self.assertEqual(pet.frame_for("happy", False), pet.FRAMES["happy"])

    def test_frame_for_blink_returns_blink_variant(self):
        self.assertEqual(pet.frame_for("happy", True), pet.FRAMES["happy_blink"])

    def test_frame_for_unknown_mood_has_no_blink_variant_and_falls_back(self):
        self.assertEqual(pet.frame_for("unknown", True), pet.FRAMES["unknown"])

    def test_mirror_frame_swaps_parens(self):
        self.assertEqual(pet.mirror_frame(["( ^‿^ )"]), [") ^‿^ ("])

    def test_step_x_walks_in_facing_direction(self):
        self.assertEqual(pet.step_x(10, 1, 100), (11, 1))
        self.assertEqual(pet.step_x(10, -1, 100), (9, -1))

    def test_step_x_bounces_at_right_edge(self):
        maxx = 20
        x, facing = pet.step_x(maxx - pet.FRAME_WIDTH, 1, maxx)
        self.assertEqual(facing, -1)
        self.assertLessEqual(x + pet.FRAME_WIDTH, maxx)

    def test_step_x_bounces_at_left_edge(self):
        self.assertEqual(pet.step_x(0, -1, 100), (0, 1))


if __name__ == "__main__":
    unittest.main()
