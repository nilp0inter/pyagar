"""
``pyagar.cmdline``
==================

Provides the cmdline facility.

"""
import argparse
import asyncio
import imp
import logging
import sys
import textwrap

from pyagar import LOOP, NICK, VERSION
from pyagar.client import Client
from pyagar.log import logger
from pyagar.utils import hub, GameplaySaver, GameReplay
from pyagar.visual import Visualizer


def pyagar_parser():
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
    parser.add_argument(
        "-r",
        "--region",
        default="EU-London")

    parser.add_argument(
        "-s",
        "--save",
        help=("Save the gameplay in a file. "
              "You can replay it later using the ``replay`` command."))

    parser.add_argument('--version', action='version',
                        version='%(prog)s ' + VERSION)

    party = parser.add_mutually_exclusive_group(required=False)
    party.add_argument('--create-party', action='store_true')
    party.add_argument('--join-party', action='store')

    # Subcommands
    subparsers = parser.add_subparsers(dest="command")

    # List regions subcommand
    subparsers.add_parser("list-regions")

    # Play subcommand
    subparsers.add_parser("play")

    # Spectate subcommand
    subparsers.add_parser("spectate")

    # Bot subcommand
    bot = subparsers.add_parser("bot")

    group = bot.add_mutually_exclusive_group(required=True)
    group.add_argument('--list-types', action='store_true')
    group.add_argument('--type', action='store')
    group.add_argument('--from-file', action='store')

    # Replay subcommand
    replay = subparsers.add_parser("replay")
    replay.add_argument('gameplay_file', nargs=1)

    return parser


def pyagar():
    """pyagar cli interface."""

    args = pyagar_parser().parse_args()
    if args.command is None:
        logger.error("No subcommand present. To play execute: 'pyagar play'")
        sys.exit(1)

    coros = []
    dsts = []

    if args.debug is not None:
        logger.setLevel(logging.DEBUG)

        if args.debug > 1:
            from pyagar.utils import Output
            output = Output()
            coros.append(output.run())
            dsts.append(output)
    else:
        logger.setLevel(logging.INFO)

    logger.info("Starting pyagar!")
    if VERSION:
        logger.info("Version %s", VERSION)

    if args.command == "replay":
        visualizer = Visualizer(
            None,
            view_only=True,
            hardware=not args.disable_hw)
        dsts.append(visualizer)
        
        replayer = GameReplay(args.gameplay_file[0])

        coros.append(replayer.run())
        coros.append(visualizer.run())
        coros.append(hub(replayer, *dsts))

    else:
        party = args.create_party or args.join_party or False
        client = Client(args.nick, region=args.region, party=party)
        coros.append(client.read())

        visualizer = Visualizer(
            client,
            view_only=args.command != "play",
            hardware=not args.disable_hw)
        coros.append(visualizer.run())
        dsts.append(visualizer)

        if args.command == "list-regions":
            from pyagar.utils import print_regions
            print_regions(client.get_regions())
            sys.exit(0)
        elif args.command == "bot":
            if args.list_types:
                print("Available bot types:\n")
                from pyagar.control import Controller
                for cls in Controller.__subclasses__():
                    doc = cls.__doc__ if cls.__doc__ else '**Not documented**'
                    dedented_text = textwrap.dedent(doc).strip()
                    name = ' * %s: ' % cls.__name__
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

        if args.save is not None:
            saver = GameplaySaver(args.save)
            coros.append(saver.run())
            dsts.append(saver)

        coros.append(hub(client, *dsts))

        LOOP.run_until_complete(client.connect())

        if args.command == "spectate":
            LOOP.run_until_complete(client.spectate())

    game = asyncio.wait(coros, return_when=asyncio.FIRST_COMPLETED)
    done, _ = LOOP.run_until_complete(game)
    for coro in done:
        try:
            coro.result()
        except:
            logger.exception("Exception running coroutine.")

    logger.info("Bye!")
