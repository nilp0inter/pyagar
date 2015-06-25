import asyncio

from client import Client
from visual import Visualizer

LOOP = asyncio.get_event_loop()
NICK = "WATCHMEN"


@asyncio.coroutine
def hub(in_queue, *out_queues):
    while True:
        data = yield from in_queue.get()
        for q in out_queues:
            q.put_nowait(data)


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
