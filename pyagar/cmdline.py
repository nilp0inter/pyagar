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


def pyagar_parser():
    """Generates the argument parser."""
    parser = argparse.ArgumentParser()

    # General options
    parser.add_argument(
        "--disable-hw",
        action="store_true",
        help="disable hardware acceleration")
    parser.add_argument(
        "-n",
        "--nick",
        help="player cell's nickname",
        default=NICK)
    parser.add_argument(
        "-d",
        "--debug",
        action="count",
        dest="debug",
        help=("enable debug mode; "
              "use multiple times to increase the debug level"))
    parser.add_argument(
        "-r",
        "--region",
        help="the region you want to connect to",
        default="EU-London")

    parser.add_argument(
        "-s",
        "--save",
        help=("save the gameplay in a file; "
              "you can replay it later using the ``replay`` command"))

    parser.add_argument('--version', action='version',
                        version='%(prog)s ' + VERSION)

    party = parser.add_mutually_exclusive_group(required=False)
    party.add_argument(
        '--create-party',
        help="create a new party and print the shared token",
        action='store_true')
    party.add_argument(
        '--join-party',
        help="join an already created party",
        action='store')

    # Subcommands
    subparsers = parser.add_subparsers(dest="command")

    # List regions subcommand
    subparsers.add_parser(
        "list-regions",
        help="print a table with the list of available regions")

    # Play subcommand
    subparsers.add_parser(
        "play",
        help="start a new game")

    # Spectate subcommand
    subparsers.add_parser(
        "spectate",
        help="connect to the server in spectator mode")

    # Bot subcommand
    bot = subparsers.add_parser(
        "bot",
        help=("like ``play`` mode but the cell is controlled by a "
              "``Controller`` class"))

    group = bot.add_mutually_exclusive_group(required=True)
    group.add_argument(
        '--list-types',
        action='store_true',
        help="print a table with the available ``Controllers``")
    group.add_argument(
        '--type',
        action='store',
        help="type of controller to use")
    group.add_argument(
        '--from-file',
        action='store',
        help="use a controller from a python file")

    # Replay subcommand
    replay = subparsers.add_parser(
        "replay",
        help="play back a recorded gameplay")
    replay.add_argument(
        'gameplay_file',
        nargs=1,
        help="full path to the record file")

    return parser


def pyagar(argv=None):
    """pyagar cli interface."""
    from pyagar.client import Client
    from pyagar.log import logger
    from pyagar.utils import hub, GameplaySaver, GameReplay
    from pyagar.visual import Visualizer

    args = pyagar_parser().parse_args(argv)
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


def winlaunch():
    import os
    BASE = os.path.join(
        os.path.realpath(os.path.dirname(__file__)), '..', '..')

    import sys
    sys.path.insert(0, os.path.join(BASE, 'pkgs'))
    
    os.environ['PYSDL2_DLL_PATH'] = os.path.join(BASE, 'lib', 'x86')
    
    from pyagar.cmdline import pyagar
    pyagar(['play'])
