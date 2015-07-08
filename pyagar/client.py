import sys
import base64
import random
import struct
import asyncio
import requests


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
    def __init__(self, nick, location='EU-London'):
        self.nick = nick
        self.location = location
        self.server = None
        self.token = None
        self.ws = None
        self.connected = asyncio.Event()
        self.messages = asyncio.Queue()

    def get_server(self):
        data = b"\n".join((self.location.encode('ascii'),
                           INIT_TOKEN.encode('ascii')))
        res = requests.post('http://m.agar.io/',
                            data=data,
                            headers={'Origin': 'http://agar.io',
                                     'User-Agent': USER_AGENT,
                                     'Referer': 'http://agar.io/'})

        self.server, self.token, _ = res.text.split('\n')
        print("Server:", self.server)
        print("Token:", self.token)

    @asyncio.coroutine
    def connect(self):
        if self.server is None:
            self.get_server()

        self.ws = yield from websockets.connect("ws://" + self.server,
                                                origin='http://agar.io')
        yield from self.ws.send(struct.pack("<BI", 254, 4))
        yield from self.ws.send(struct.pack("<BI", 255, int(INIT_TOKEN)))

        # Send token
        msg = struct.pack("B" + ("B" * len(self.token)),
                          80, *[ord(c) for c in self.token])

        yield from self.ws.send(msg)
        self.connected.set()

    @asyncio.coroutine
    def spawn(self):
        yield from self.connected.wait()
        rawnick = self.nick.encode('utf-8')
        msg = struct.pack("<B" + ("H" * len(rawnick)),
                          0, *rawnick)
        yield from self.ws.send(msg)

    @asyncio.coroutine
    def read(self):
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
                print(msg.msgtype)
            else:
                yield from self.messages.put(msg.data)

    @asyncio.coroutine
    def move(self, x, y):
        yield from self.connected.wait()
        yield from self.ws.send(struct.pack("<BddI", 16, x, y, 0))

    @asyncio.coroutine
    def spectate(self):
        yield from self.connected.wait()
        yield from asyncio.sleep(2)
        yield from self.ws.send(struct.pack("B", 1))
