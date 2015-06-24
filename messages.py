from abc import ABCMeta, abstractmethod
from collections import namedtuple
from enum import Enum
from itertools import count
import struct

UINT8   = "B"
INT8    = "b"
UINT16  = "H"
INT16   = "h"
UINT32  = "I"
INT32   = "i"
UINT64  = "Q"
INT64   = "q"
FLOAT32 = "f"
FLOAT64 = "d"

Cell = namedtuple("Cell", ['id', 'x', 'y', 'size', 'color', 'is_virus',
                           'name'])
Screen = namedtuple("Screen", ["x1", "y1", "x2", "y2"])
Camera = namedtuple("Camera", ["x", "y", "zoom"])
Player = namedtuple("Player", ["id", "name"])
Eat = namedtuple("Eat", ["eater", "eatee"])
Dissapear = namedtuple("Dissapear", ["id"])
PlayerID = namedtuple("PlayerID", ["id"])


class BaseMSG(metaclass=ABCMeta):
    def __init__(self, buf, offset=0):
        self.buf = buf
        self.offset = offset
        self.parse()

    def get(self, ctype):
        s = struct.unpack_from(ctype, self.buf, offset=self.offset)
        self.offset += struct.calcsize(ctype)
        if len(s) == 1:
            return s[0]
        else:
            return list(s)

    def getUint8(self):
        return self.get(UINT8)

    def getInt8(self):
        return self.get(INT8)

    def getUint16(self):
        return self.get(UINT16)

    def getInt16(self):
        return self.get(INT16)

    def getUint32(self):
        return self.get(UINT32)

    def getInt32(self):
        return self.get(INT32)

    def getFloat32(self):
        return self.get(FLOAT32)

    def getUint64(self):
        return self.get(UINT64)

    def getInt64(self):
        return self.get(INT64)

    def getFloat64(self):
        return self.get(FLOAT64)

    def string(self, ctype=UINT16): 
        bls = struct.calcsize(ctype)
        def _get():
            while True:
                d = struct.unpack_from(ctype, self.buf, offset=self.offset)[0]
                self.offset += bls
                if d == 0:
                    break
                else:
                    yield d

        return "".join(chr(c) for c in _get())

    @abstractmethod
    def parse(self):
        pass


class Status(BaseMSG):
    def parse(self):
        self.cells = []
        self.eat = []

        self.num = self.getUint16()
        for i in range(self.num):
            self.eat.append(Eat(eater=self.getUint32(),
                                eatee=self.getUint32()))

        for i in count():
            _id = self.getUint32()
            if _id == 0:
                break

            x = self.getInt16()
            y = self.getInt16()
            size = self.getInt16()

            # Get Cell Color
            color = "%06x" % (self.getUint8() << 16 |
                              self.getUint8() << 8  |
                              self.getUint8())

            k = self.getUint8() 
            is_virus = bool(k & 1)
            r = (k & 16)

            if k & 2:
                self.offset += 4
            elif k & 4:
                self.offset += 8
            elif k & 8:
                self.offset += 16

            name = self.string() or None
            self.cells.append(Cell(_id, x, y, size, color, is_virus, name))

        self.balls_on_screen = self.getUint32()
        self.dissapears = []
        for i in range(self.balls_on_screen):
            self.dissapears.append(Dissapear(self.getUint32()))

    def __repr__(self):
        return "Eat=%r\nCells=%r\nDissapears=%r\n" % (self.eat, self.cells,
                                                      self.dissapears)


class Leaderboard(BaseMSG):
    def parse(self):
        self.players = []
        for i in range(self.getUint32()):
            self.players.append(Player(id=self.getUint32(),
                                       name=self.string()))

    def __repr__(self):
        return repr(self.players)


class TeamsScore(BaseMSG):
    def parse(self):
        self.numplayers = self.getUint32()
        self.players = [self.getFloat32() for i in range(self.numplayers)]

    def __repr__(self):
        return repr(self.players)


class ScreenAndCamera(BaseMSG):
    def parse(self):
        self.screen = Screen(x1=self.getFloat64(),
                             y1=self.getFloat64(),
                             x2=self.getFloat64(),
                             y2=self.getFloat64())

        self.camera = Camera(x=(self.screen.x2 + self.screen.x1) / 2,
                             y=(self.screen.y2 + self.screen.y1) / 2,
                             zoom=1)

    def __repr__(self): 
        return "%s %s" % (self.screen, self.camera)


class CameraPosition(BaseMSG):
    def parse(self):
        self.camera = Camera(x=self.getFloat32(),
                             y=self.getFloat32(),
                             zoom=self.getFloat32())

    def __repr__(self):
        return repr(self.camera)


class PlayerCell(BaseMSG):
    def parse(self):
        self.cell = PlayerID(self.getUint32())

    def __repr__(self):
        return repr(self.cell)


class ResetSomething(BaseMSG):
    def parse(self):
        pass


class SetQARA(BaseMSG):
    def parse(self):
        self.ca = self.getInt16()
        self.da = self.getInt16()
        self.sa = True


class MSGType(Enum):
    Status = 16
    CameraPosition = 17
#    ResetSomething = 20
#    SetQARA = 21
    PlayerCell = 32
    Leaderboard = 49
    TeamsScore = 50
    ScreenAndCamera = 64

    @property
    def cls(self):
        return globals().get(self.name)


class MSG(BaseMSG):
    def parse(self):
        c = self.get("B")
        if c == 240:
            self.offset += 5
            c = self.get("B")

        self.msgtype = c
        try:
            msgcls = MSGType(self.msgtype).cls
        except ValueError:
            self.data = None
        else:
            self.data = msgcls(self.buf, self.offset)

    def __repr__(self):
        if self.data is not None:
            return repr(self.data)
        else:
            return repr(self.msgtype)
