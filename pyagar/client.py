"""
``pyagar.client``
=================

This module contains the Client class.

"""
# pylint: disable=I0011,C0103
import base64
import random
import struct
import asyncio
import requests


from pyagar.log import logger


INIT_TOKEN = '154669603'
USER_AGENT = (
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) '
    'Chrome/43.0.2357.125 Safari/537.36')

#
# <monkeypatch>
# Monkeypatch the websockets library to bypass agar.io "limitations".
#
from websockets import client

def build_request(set_header):
    """
    Build a handshake request to send to the server.

    Return the `key` which must be passed to :func:`check_response`.
    """
    rand = bytes(random.getrandbits(8) for _ in range(16))
    key = base64.b64encode(rand).decode()
    set_header('Connection', 'Upgrade')
    set_header('Sec-WebSocket-Extensions', 'permessage-deflate; client_max_window_bits')
    set_header('Sec-WebSocket-Key', key)
    set_header('Sec-WebSocket-Version', '13')
    set_header('Upgrade', 'websocket')
    return key

client.USER_AGENT = USER_AGENT
client.build_request = build_request
#
# </monkeypatch>
#
from pyagar import messages
import websockets


class Client:
    """
    The client.

    Manages the connection, receives the data from the server and sends
    back any command requested by the player.

    """
    def __init__(self, nick, location='EU-London'):
        self.nick = nick
        self.location = location
        self.server = None
        self.token = None
        self.ws = None
        self.connected = asyncio.Event()
        self.messages = asyncio.Queue()


    @classmethod
    def get_regions(cls):
        """Request the list of regions."""
        res = requests.get('https://m.agar.io/info')
        return res.json().get('regions', {})

    def get_server(self):
        """Requests a new server and token."""
        data = b"\n".join((self.location.encode('ascii'),
                           INIT_TOKEN.encode('ascii')))
        res = requests.post('http://m.agar.io/',
                            data=data,
                            headers={'Origin': 'http://agar.io',
                                     'User-Agent': USER_AGENT,
                                     'Referer': 'http://agar.io/'})

        self.server, self.token, _ = res.text.split('\n')
        logger.debug("Server: %s", self.server)
        logger.debug("Token: %s", self.token)

    @asyncio.coroutine
    def connect(self):
        """Connects to the server."""
        if self.server is None:
            self.get_server()

        logger.info("Connecting to server %s", self.server)
        self.ws = yield from websockets.connect("ws://" + self.server,
                                                origin='http://agar.io')
        yield from self.ws.send(struct.pack("<BI", 254, 4))
        yield from self.ws.send(struct.pack("<BI", 255, int(INIT_TOKEN)))

        # Send token
        msg = struct.pack("B" + ("B" * len(self.token)),
                          80, *[ord(c) for c in self.token])

        yield from self.ws.send(msg)
        logger.debug("Connected!")
        self.connected.set()

    @asyncio.coroutine
    def spawn(self):
        """Sends the ``spawn`` command."""
        yield from self.connected.wait()
        rawnick = self.nick.encode('utf-8')
        msg = struct.pack("<B" + ("H" * len(rawnick)),
                          0, *rawnick)
        yield from self.ws.send(msg)
        logger.debug("Spawn sent.")

    @asyncio.coroutine
    def split(self):
        """Sends the ``split cell`` command."""
        yield from self.connected.wait()
        msg = struct.pack("<B", 17)
        yield from self.ws.send(msg)
        logger.debug("Split sent.")

    @asyncio.coroutine
    def eject(self):
        """Sends the ``mass eject`` command."""
        yield from self.connected.wait()
        msg = struct.pack("<B", 21)
        yield from self.ws.send(msg)
        logger.debug("Eject sent.")

    @asyncio.coroutine
    def read(self):
        """Read, decode and queue data packets from the server."""
        while True:
            yield from self.connected.wait()
            data = yield from self.ws.recv()
            if data is None:
                self.connected.clear()
                self.server = self.token = None
                yield from self.connect()
                continue
            msg = messages.MSG(data)
            if msg.data is None:
                logger.warning("Unknown message %r", msg)
            else:
                yield from self.messages.put(msg.data)

    @asyncio.coroutine
    def move(self, x, y):
        """Sends the ``movement`` command."""
        yield from self.connected.wait()
        yield from self.ws.send(struct.pack("<BddI", 16, x, y, 0))
        logger.debug("Move sent (x=%s, y=%s)", x, y)

    @asyncio.coroutine
    def spectate(self):
        """Initiates the spectator mode."""
        yield from self.connected.wait()
        yield from asyncio.sleep(2)
        yield from self.ws.send(struct.pack("B", 1))
        logger.debug("Spectate sent.")
