import argparse
import asyncio
import imp
import logging
import sys
import textwrap

from pyagar import LOOP, NICK, VERSION, hub
from pyagar.client import Client
from pyagar.log import logger
from pyagar.visual import Visualizer


def parser():
    """Generates the argument parser."""
    parser = argparse.ArgumentParser()

    # General options
    parser.add_argument(
        "--disable-hw",
        action="store_true",
        help="Disable hardware acceleration.")
    parser.add_argument(
        "-n",
        "--nick",
        default=NICK)
    parser.add_argument(
        "-d",
        "--debug",
        action="count",
        dest="debug",
        help=("Enable debug mode. "
              "Use multiple times to increase the debug level."))

    parser.add_argument('--version', action='version',
                        version='%(prog)s ' + VERSION)

    # Subcommands
    subparsers = parser.add_subparsers(dest="command")

    # Play subcommand
    play = subparsers.add_parser("play")

    # Spectate subcommand
    spectate = subparsers.add_parser("spectate")

    # Bot subcommand
    bot = subparsers.add_parser("bot")

    group = bot.add_mutually_exclusive_group(required=True)
    group.add_argument('--list-types', action='store_true')
    group.add_argument('--type', action='store')
    group.add_argument('--from-file', action='store')

    return parser


def pyagar():
    """pyagar cli interface."""

    args = parser().parse_args()
    if args.command is None:
        logger.error("No subcommand present. To play execute: 'pyagar play'")
        sys.exit(1)

    client = Client(args.nick)

    coros = [client.read()]

    dsts = []

    visualizer = Visualizer(
        client,
        view_only=args.command != "play",
        hardware=not args.disable_hw)
    coros.append(visualizer.run())
    dsts.append(visualizer)

    if args.debug is not None:
        logger.setLevel(logging.DEBUG)

        if args.debug > 1:
            from pyagar import Output
            output = Output()
            coros.append(output.run())
            dsts.append(output)
    else:
        logger.setLevel(logging.INFO)

    if args.command == "bot":
        if args.list_types:
            print("Available bot types:\n")
            from pyagar.control import Controller
            for c in Controller.__subclasses__():
                doc = c.__doc__ if c.__doc__ else '**Not documented**'
                dedented_text = textwrap.dedent(doc).strip()
                name = ' * %s: ' % c.__name__
                msg = textwrap.fill(
                    dedented_text,
                    initial_indent=name,
                    subsequent_indent='    ')
                print(msg)
            sys.exit(0)
        elif args.type:
            from pyagar import control
            if not hasattr(control, args.type):
                print("Unknown bot type")
                sys.exit(1)
            else:
                bot = getattr(control, args.type)
                if (not issubclass(bot, control.Controller) or
                        bot is control.Controller):
                    print("Invalid bot type.")
                    sys.exit(1)
                else:
                    controller = bot(client)
                    coros.append(controller.run())
                    dsts.append(controller)
        elif args.from_file:
            from pyagar.control import Controller
            module = imp.load_source('botmodule', args.from_file)
            if (not hasattr(module, 'UserBot') or
                    not issubclass(module.UserBot, Controller)):
                print("Invalid bot.")
            else:
                controller = module.UserBot(client)
                coros.append(controller.run())
                dsts.append(controller)

    coros.append(hub(client, *dsts))

    logger.info("Starting pyagar!")
    if VERSION:
        logger.info("Version %s", VERSION)

    LOOP.run_until_complete(client.connect())

    if args.command == "spectate":
        LOOP.run_until_complete(client.spectate())

    game = asyncio.wait(coros, return_when=asyncio.FIRST_COMPLETED)
    done, not_done = LOOP.run_until_complete(game)
    for coro in done:
        try:
            res = coro.result()
        except:
            logger.exception("Exception running coroutine.")

    logger.info("Bye!")
