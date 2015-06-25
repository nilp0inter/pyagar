import asyncio

from client import Client
from visual import Visualizer
from control import EatWhenNoPredators, Escape, Closer, Greedy

LOOP = asyncio.get_event_loop()
NICK = "WATCHMEN"


@asyncio.coroutine
def hub(src, *dsts):
    """Broadcasts msgs from ``src.messages`` to all ``dsts.messages``."""
    src_q = src.messages
    dst_qs = [d.messages for d in dsts]
    while True:
        data = yield from src_q.get()
        for q in dst_qs:
            q.put_nowait(data)


@asyncio.coroutine
def output(client):
    while True:
        data = yield from client.messages.get()
        print(data)


def main():
    client = Client(NICK)
    visualizer = Visualizer(client, view_only=False)
    controller = EatWhenNoPredators(client)

    coros = asyncio.wait([
        client.connect(),
        client.read(),
        hub(client, visualizer, controller),
        visualizer.run(),
        controller.run()
        # client.spectate(),
    ])
    LOOP.run_until_complete(coros)


if __name__ == '__main__':
    main()
