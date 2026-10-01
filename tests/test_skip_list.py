import random
import unittest

from skip_list import ScenarioSkipList


class SkipListTests(unittest.TestCase):
    def setUp(self) -> None:
        self.rng = random.Random(0)
        self.sl = ScenarioSkipList(self.rng)
        self.sl.bulk_load_classes(["Amphibia", "Aves", "Mammalia", "Reptilia"])

    def test_nodes_and_levels(self) -> None:
        self.assertEqual(self.sl.size, 4)
        self.assertGreaterEqual(self.sl.level, 1)
        for node in self.sl.buildings:
            self.assertEqual(len(node.forward), node.level)

    def test_move_consumes_single_hop(self) -> None:
        cur = self.sl.head
        lvl = 0
        self.assertTrue(self.sl.can_move(cur, 0, lvl))
        nxt = self.sl.move(cur, 0, lvl)
        self.assertIsNotNone(nxt)
        assert nxt is not None
        self.assertEqual(nxt.idx, 1)

    def test_upper_level_can_skip(self) -> None:
        cur = self.sl.head
        top = self.sl.height_of(cur) - 1
        moves = self.sl.get_available_moves(cur, 0)
        levels = [m[0] for m in moves]
        self.assertIn(0, levels)
        if top > 0 and self.sl.can_move(cur, 0, top):
            far = self.sl.move(cur, 0, top)
            self.assertIsNotNone(far)
            assert far is not None
            self.assertGreater(far.idx, 1)

    def test_target_building_lookup(self) -> None:
        node = self.sl.node_for_class("Aves")
        self.assertIsNotNone(node)
        assert node is not None
        self.assertEqual(node.animal_class, "Aves")


if __name__ == "__main__":
    unittest.main()
