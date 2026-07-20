from __future__ import annotations

import unittest
from unittest.mock import patch

from displayctl import move


class MoveTests(unittest.TestCase):
    def test_split_uses_shared_state_transition(self) -> None:
        left = {"id": 10, "frame": {"x": 0}}
        right = {"id": 20, "frame": {"x": 100}}

        with (
            patch.object(move, "_eligible_windows", return_value=[left, right]),
            patch.object(move, "_split_state", return_value="half"),
            patch.object(move, "_set_split_layout") as set_layout,
        ):
            move.split()

        set_layout.assert_called_once_with(left, right, "weighted")

    def test_framed_split_preserves_existing_cycle(self) -> None:
        left = {"id": 10, "frame": {"x": 0}}
        right = {"id": 20, "frame": {"x": 100}}

        with (
            patch.object(move, "_eligible_windows", return_value=[left, right]),
            patch.object(move, "_split_state", return_value="framed_weighted"),
            patch.object(move, "_set_split_layout") as set_layout,
        ):
            move.split(frame=True)

        set_layout.assert_called_once_with(left, right, "framed_half")

    def test_tile_reuses_window_query_when_falling_back_to_quad(self) -> None:
        wins = [{"id": 10}]
        with (
            patch.object(move, "_eligible_windows", return_value=wins) as eligible,
            patch.object(move, "_quad") as quad,
        ):
            move.tile()

        eligible.assert_called_once_with(limit=4)
        quad.assert_called_once_with(wins)


if __name__ == "__main__":
    unittest.main()
