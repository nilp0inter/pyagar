"""
``pyagar.utils``
================

Non categorized stuff.

"""
# pylint: disable=I0011,R0903
import asyncio
import atexit
import pickle
import time

from pyagar.log import logger


@asyncio.coroutine
def hub(src, *dsts):
    """Broadcasts msgs from ``src.messages`` to all ``dsts.messages``."""
    src_q = src.messages
    dst_qs = [d.messages for d in dsts]
    while True:
        data = yield from src_q.get()
        for queue in dst_qs:
            queue.put_nowait(data)


class Output:
    """Prints every message received."""
    def __init__(self):
        self.messages = asyncio.Queue()

    @asyncio.coroutine
    def run(self):
        """Logs all everything."""
        while True:
            data = yield from self.messages.get()
            logger.debug(data)


class GameplaySaver:
    """Store the gameplay messages in a file with a timestamp."""
    def __init__(self, filename):
        self.messages = asyncio.Queue()
        self.filename = filename

    @asyncio.coroutine
    def run(self):
        with open(self.filename, 'wb') as fd:
            while True:
                data = yield from self.messages.get()
                pickle.dump((time.monotonic(), data), fd)


class GameReplay:
    """Replay the messages saved with ``GameplaySaver``."""
    def __init__(self, filename):
        self.messages = asyncio.Queue()
        self.filename = filename
        self.fd = None
        self.last = None

    def unpack_next(self):
        try:
            data = pickle.load(self.fd)
        except EOFError:
            return (None, None)
        else:
            timestamp, msg = data

            if self.last is None:
                delay = 0
            else:
                delay = timestamp - self.last

            self.last = timestamp

            return (delay, msg)

    @asyncio.coroutine
    def run(self):
        with open(self.filename, 'rb') as self.fd:
            while True:
                delta, data = self.unpack_next()
                if data is None:
                    break
                else:
                    yield from asyncio.sleep(delta)
                    yield from self.messages.put(data)


def print_regions(regions):
    """Prints a pretty table with the region data."""
    from tabulate import tabulate
    headers = ["Region", "numServers", "numRealms", "numPlayers"]
    table = [[k, v["numServers"], v["numRealms"], v["numPlayers"]]
             for k, v in sorted(regions.items())]
    print(tabulate(table, headers, tablefmt="rst"))
