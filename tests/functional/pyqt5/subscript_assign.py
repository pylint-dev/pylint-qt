"""Regression test: subscript assignment on a plain list attribute is not E1137."""

# pylint: disable=missing-docstring,too-few-public-methods,unused-import
import PyQt5


class Game:
    """A game with players."""

    players: list[str]


game = Game()
game.players = ["list"]
# False positive: E1137 should NOT be raised here
game.players[0] = "new player"
