import argparse
import asyncio
import logging

from pyagar import LOOP, NICK, VERSION, hub
from pyagar.client import Client
from pyagar.log import logger


def parser():
    """Generates the argument parser."""
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

    return parser


def pyagar():
    """pyagar cli interface."""

    args = parser().parse_args()

    client = Client(args.nick)

    coros = [client.read()]

    dsts = []

    if not args.no_visualize:
        from pyagar.visual import Visualizer
        visualizer = Visualizer(
            client,
            view_only=args.spectate or args.auto,
            hardware=not args.disable_hw)
        coros.append(visualizer.run())
        dsts.append(visualizer)

    if args.auto:
        from pyagar.control import EatWhenNoPredators
        controller = EatWhenNoPredators(client)
        coros.append(controller.run())
        dsts.append(controller)

    if args.debug is not None:
        logger.setLevel(logging.DEBUG)

        if args.debug > 1:
            from pyagar import Output
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
