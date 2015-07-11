import asyncio
import pkg_resources


LOOP = asyncio.get_event_loop()
NICK = "pyagar"
try:
    VERSION = pkg_resources.get_distribution("pyagar").version
except:
    VERSION = None


@asyncio.coroutine
def hub(src, *dsts):
    """Broadcasts msgs from ``src.messages`` to all ``dsts.messages``."""
    src_q = src.messages
    dst_qs = [d.messages for d in dsts]
    while True:
        data = yield from src_q.get()
        for q in dst_qs:
            q.put_nowait(data)


class Output:
    def __init__(self):
        self.messages = asyncio.Queue()

    @asyncio.coroutine
    def run(self):
        while True:
            data = yield from self.messages.get()
            logger.debug(data)
