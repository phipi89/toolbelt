from __future__ import annotations

import sys
import unittest
from unittest.mock import patch

from displayctl import cli


class CliTests(unittest.TestCase):
    def test_place_forwards_keep_size_and_toggle(self) -> None:
        with (
            patch.object(
                sys, "argv", ["displayctl", "place", "--keep-size", "--toggle"]
            ),
            patch.object(cli.move, "place") as place,
        ):
            cli.main()

        place.assert_called_once_with(keep_size=True, toggle=True)

    def test_place_defaults_to_resizing_placement(self) -> None:
        with (
            patch.object(sys, "argv", ["displayctl", "place"]),
            patch.object(cli.move, "place") as place,
        ):
            cli.main()

        place.assert_called_once_with(keep_size=False, toggle=False)


if __name__ == "__main__":
    unittest.main()
