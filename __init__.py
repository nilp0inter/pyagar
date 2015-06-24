import asyncio

from client import Client
from visual import Visualizer
from hub import hub

LOOP = asyncio.get_event_loop()
NICK = "WATCHMEN"


@asyncio.coroutine
def output(client):
    while True:
        data = yield from client.messages.get()
        print(data)


def main():
    client = Client(NICK)
    visualizer = Visualizer(client)

    coros = asyncio.wait([
        client.connect(),
        client.read(),
        hub(client.messages, visualizer.messages),
        visualizer.run(),
    ])
    LOOP.run_until_complete(coros)


if __name__ == '__main__':
    main()
