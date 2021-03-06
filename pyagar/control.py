"""
``pyagar.controller``
=====================

Some very simple bots.

"""
# pylint: disable=I0011,C0103
from collections import namedtuple
import asyncio

from pyagar.log import logger
from pyagar.messages import Status, PlayerCell, ScreenAndCamera

Movement = namedtuple('Movement', ['x', 'y'])


class Controller:
    """
    All bots should inherit from this class.

    """
    def __init__(self, client):
        self.client = client
        self.messages = asyncio.Queue()
        self.cells = {}
        self.player_id = None
        self.alive = False
        self.screen = None

    def get_name(self):
        """Returns the name of this bot."""
        if not hasattr(self, 'name'):
            return self.__class__.__name__
        else:
            return getattr(self, 'name')

    def get_movement(self):
        """The method that subclasses must implement."""
        raise NotImplementedError()

    @property
    def predators(self):
        """Cells that can eat me."""
        p = self.player
        if p:
            return [c for c in self.opponents if c.size > p.size * 1.1]
        else:
            return []

    @property
    def edible(self):
        """You can eat cells 10% smaller than you."""
        p = self.player
        if p:
            return [c for c in self.opponents if c.size * 1.1 < p.size]
        else:
            return []

    @property
    def player(self):
        """Returns the player main cell. None if not exists."""
        return self.cells.get(self.player_id)

    @property
    def viruses(self):
        """Returns a list of visible viruses."""
        return [c for c in self.cells.values() if c.is_virus]

    @property
    def opponents(self):
        """Return list of other cells."""
        return [c for c in self.cells.values()
                if c.id != self.player_id and not c.is_virus]

    @asyncio.coroutine
    def do_move(self):
        """Make a movement."""
        m = self.get_movement()
        if m is not None:
            yield from self.client.move(m.x, m.y)

    @asyncio.coroutine
    def run(self):
        """The main loop of the bot."""
        logger.info("Running bot '%s'", self.get_name())

        while True:
            data = yield from self.messages.get()
            if isinstance(data, Status):
                for cell in data.cells:
                    self.cells[cell.id] = cell
                for cell in data.dissapears:
                    if cell.id in self.cells:
                        del self.cells[cell.id]
                for eats in data.eat:
                    if eats.eatee == self.player_id:
                        self.alive = False
                    if eats.eatee in self.cells:
                        del self.cells[eats.eatee]
            elif isinstance(data, PlayerCell):
                self.player_id = data.cell.id
                self.alive = True
            elif isinstance(data, ScreenAndCamera):
                self.screen = data.screen
            else:
                pass

            if not self.alive:
                yield from self.client.spawn()
            yield from self.do_move()


class Closer(Controller):
    """Go to the closer "non-virus" cell, no matter the type."""
    def get_movement(self):
        p = self.player
        o = self.opponents
        if p and o:
            closer = min(o, key=lambda c: abs(c.x-p.x)+abs(c.y-p.y))
            return Movement(closer.x, closer.y)
        else:
            return None


class Greedy(Controller):
    """Only wants to eat."""
    def get_movement(self):
        o = self.edible
        p = self.player
        if o and p:
            closer = min(o, key=lambda c: abs(c.x-p.x)+abs(c.y-p.y))
            return Movement(closer.x, closer.y)
        else:
            return None


class Escape(Controller):
    """Escape from bigger opponents."""

    @staticmethod
    def escape_vector(player, cell):
        """Movement to escape from a cell."""
        ox = (cell.x - player.x)
        oy = (cell.y - player.y)

        return Movement(player.x - ox,
                        player.y - oy)

    def compound_escape_vector(self, vectors, cells):
        """Returns the sum of all ``vectors``."""
        p = self.player

        xs = [c.x - p.x for c in vectors]
        ys = [c.y - p.y for c in vectors]

        vs = [(x, y, c.size) for x, y, c in zip(xs, ys, cells)]

        x = sum(s / 2 * x for x, _, s in vs if x != 0) * 300
        y = sum(s / 2 * y for _, y, s in vs if y != 0) * 300

        return Movement(x=p.x + x,
                        y=p.y + y)

    def get_movement(self):
        p = self.player
        o = self.predators

        if p and o:
            vectors = [self.escape_vector(p, c) for c in o]
            return self.compound_escape_vector(vectors, o)
        elif p:
            return Movement(x=p.x, y=p.y)


class Center(Controller):
    """Go to the center."""
    def get_movement(self):
        if self.player and self.screen:
            return Movement(x=self.screen.x2 / 2, y=self.screen.y2 / 2)


class EatWhenNoPredators(Escape, Greedy, Center, Controller):
    """Only eats when all visible cells are smaller then itself."""
    escape = Escape.get_movement
    eat = Greedy.get_movement
    nothing_to_do = Center.get_movement

    def get_movement(self):
        p = self.player
        if p:
            if not self.predators:
                if self.edible:
                    return self.eat()
                else:
                    return self.nothing_to_do()
            else:
                return self.escape()
        else:
            return None
