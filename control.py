import asyncio
from collections import namedtuple
from messages import Status, PlayerCell, ScreenAndCamera

Movement = namedtuple('Movement', ['x', 'y'])


class Controller:
    def __init__(self, client):
        self.client = client
        self.messages = asyncio.Queue()
        self.cells = {}
        self.player_id = None
        self.alive = False
        self.screen = None

    def get_movement(self):
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
        return self.cells.get(self.player_id)

    @property
    def viruses(self):
        return [c for c in self.cells.values() if c.is_virus]

    @property
    def opponents(self):
        """Return list of other cells."""
        return [c for c in self.cells.values()
                if c.id != self.player_id and not c.is_virus]

    @asyncio.coroutine
    def do_move(self):
        m = self.get_movement()
        if m is not None:
            yield from self.client.move(m.x, m.y)

    @asyncio.coroutine
    def run(self):
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
            food = max(o, key=lambda c: (-1*(abs(p.x-c.x)+abs(p.x-c.x)), 0))
            return Movement(food.x, food.y)
        else:
            return None


class Escape(Controller):
    """Escape from bigger opponents."""

    def escape_vector(self, player, cell):
        """Movement to escape from a cell."""
        ox = (cell.x - player.x)
        oy = (cell.y - player.y)

        return Movement(player.x - ox,
                        player.y - oy)

    def compound_escape_vector(self, vectors):
        p = self.player
        xs = [c.x - p.x for c in vectors]
        ys = [c.y - p.y for c in vectors]

        x=sum(xs)
        y=sum(ys)

        return Movement(x=p.x+x, y=p.y+y)

    def get_movement(self):
        p = self.player
        o = self.predators

        if p and o:
            vectors = [self.escape_vector(p, c) for c in o]
            return self.compound_escape_vector(vectors)
        elif p:
            return Movement(x=p.x, y=p.y)


class Center(Controller):
    """Go to the center."""
    def get_movement(self):
        if self.player and self.screen:
            return Movement(x=self.screen.x2 / 2, y=self.screen.y2 / 2)


class EatWhenNoPredators(Escape, Greedy, Center):
    escape = Escape.get_movement
    eat = Greedy.get_movement
    nothing_to_do = Center.get_movement

    def get_movement(self):
        p = self.player
        o = self.predators
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
