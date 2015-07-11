import argparse
import asyncio
import logging
import pkg_resources
import sys

from pyagar.log import logger
from pyagar.client import Client
from pyagar.visual import Visualizer
from pyagar.control import EatWhenNoPredators, Escape, Closer, Greedy

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


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument("--no-visualize", action="store_true")
    parser.add_argument("--disable-hw",
                        action="store_true",
                        help="Disable hardware acceleration.")
    parser.add_argument("-n", "--nick", default=NICK)
    parser.add_argument("--auto", action="store_true")
    parser.add_argument(
        "-d",
        action="count",
        dest="debug",
        help=("Enable debug mode. "
              "Use multiple times to increase the debug level."))
    parser.add_argument("--spectate", action="store_true")
    args = parser.parse_args()

    client = Client(args.nick)

    coros = [client.read()]

    dsts = []

    if not args.no_visualize:
        visualizer = Visualizer(
            client,
            view_only=args.spectate or args.auto,
            hardware=not args.disable_hw)
        coros.append(visualizer.run())
        dsts.append(visualizer)

    if args.auto:
        controller = EatWhenNoPredators(client)
        coros.append(controller.run())
        dsts.append(controller)

    if args.debug is not None:
        logger.setLevel(logging.DEBUG)

        if args.debug > 1:
            output = Output()
            coros.append(output.run())
            dsts.append(output)
    else:
        logger.setLevel(logging.INFO)


    coros.append(hub(client, *dsts))

    logger.info("Starting pyagar!")
    if VERSION:
        logger.info("Version %s", VERSION)

    LOOP.run_until_complete(client.connect())

    if args.spectate:
        LOOP.run_until_complete(client.spectate())

    game = asyncio.wait(coros, return_when=asyncio.FIRST_COMPLETED)
    done, not_done = LOOP.run_until_complete(game)
    for coro in done:
        try:
            res = coro.result()
        except:
            logger.exception("Exception running coroutine.")

    logger.info("Bye!")


if __name__ == '__main__':
    main()
