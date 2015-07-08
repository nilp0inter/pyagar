import argparse
import asyncio
import sys

from pyagar.client import Client
from pyagar.visual import Visualizer
from pyagar.control import EatWhenNoPredators, Escape, Closer, Greedy

LOOP = asyncio.get_event_loop()
NICK = "pyagar"


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
            print(data)


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument("--no-visualize", action="store_true")
    parser.add_argument("-n", "--nick", default=NICK)
    parser.add_argument("--auto", action="store_true")
    parser.add_argument("--debug", action="store_true")
    parser.add_argument("--spectate", action="store_true")
    args = parser.parse_args()

    client = Client(args.nick)

    coros = [client.read()]

    dsts = []

    if not args.no_visualize:
        visualizer = Visualizer(client, view_only=args.spectate or args.auto)
        coros.append(visualizer.run())
        dsts.append(visualizer)

    if args.auto:
        controller = EatWhenNoPredators(client)
        coros.append(controller.run())
        dsts.append(controller)

    if args.debug:
        output = Output()
        coros.append(output.run())
        dsts.append(output)

    if args.spectate:
        coros.append(client.spectate())

    coros.append(hub(client, *dsts))

    print("Connecting...")
    LOOP.run_until_complete(client.connect())

    print("Starting!")
    LOOP.run_until_complete(asyncio.wait(coros))


if __name__ == '__main__':
    main()
