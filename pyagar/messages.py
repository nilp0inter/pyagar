"""
``pyagar.messages``
===================

Protocol implementation.

"""
# pylint: disable=I0011,C0103
from abc import ABCMeta, abstractmethod
from collections import namedtuple
from enum import Enum
import struct

INT8 = "b"
INT16 = "h"
INT32 = "i"
INT64 = "q"
UINT8 = "B"
UINT16 = "H"
UINT32 = "I"
UINT64 = "Q"
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
    """
    All messages inherits from this class.

    Contains utility methods for unpack the data.

    """
    def __init__(self, buf, offset=0):
        self.buf = buf
        self.offset = offset
        self.parse()

    def get(self, ctype):
        """Unpack the given ``ctype`` and update the offset."""
        s = struct.unpack_from(ctype, self.buf, offset=self.offset)
        self.offset += struct.calcsize(ctype)
        if len(s) == 1:
            return s[0]
        else:
            return list(s)

    def getUint8(self):
        """Unpack an ``UINT8``."""
        return self.get(UINT8)

    def getInt8(self):
        """Unpack an ``INT8``."""
        return self.get(INT8)

    def getUint16(self):
        """Unpack an ``UINT16``."""
        return self.get(UINT16)

    def getInt16(self):
        """Unpack an ``INT16``."""
        return self.get(INT16)

    def getUint32(self):
        """Unpack an ``UINT32``."""
        return self.get(UINT32)

    def getInt32(self):
        """Unpack an ``INT32``."""
        return self.get(INT32)

    def getFloat32(self):
        """Unpack an ``FLOAT32``."""
        return self.get(FLOAT32)

    def getUint64(self):
        """Unpack an ``UINT64``."""
        return self.get(UINT64)

    def getInt64(self):
        """Unpack an ``INT64``."""
        return self.get(INT64)

    def getFloat64(self):
        """Unpack an ``FLOAT64``."""
        return self.get(FLOAT64)

    def string(self, ctype=UINT16):
        """Unpack a string."""
        bls = struct.calcsize(ctype)
        def _get():
            """Generate the secuence of characters to the Null."""
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
        """This method must be implemented in the message subclass."""
        pass


class Status(BaseMSG):
    """
    The status of the stage.

    Who eats who, what is visible, what dissapears...

    """
    def parse(self):
        """Unpacks the data."""
        self.cells = []
        self.eat = []

        self.num = self.getUint16()
        for _ in range(self.num):
            self.eat.append(Eat(eater=self.getUint32(),
                                eatee=self.getUint32()))

        _id = self.getUint32()
        while _id != 0:
            x = self.getInt32()
            y = self.getInt32()
            size = self.getInt16()

            # Get Cell Color
            color = "%06x" % (self.getUint8() << 16 |
                              self.getUint8() << 8  |
                              self.getUint8())

            k = self.getUint8()
            is_virus = bool(k & 1)
            # r = (k & 16)

            if k & 2:
                self.offset += 4
            elif k & 4:
                self.offset += 8
            elif k & 8:
                self.offset += 16

            name = self.string() or None
            self.cells.append(Cell(_id, x, y, size, color, is_virus, name))

            _id = self.getUint32()

        self.balls_on_screen = self.getUint32()
        self.dissapears = []
        for _ in range(self.balls_on_screen):
            self.dissapears.append(Dissapear(self.getUint32()))

    def __repr__(self):
        return "Eat=%r\nCells=%r\nDissapears=%r\n" % (self.eat, self.cells,
                                                      self.dissapears)


class Leaderboard(BaseMSG):
    """
    The ``Leaderboard``.

    The top bigger cells in descending order.

    This message is only received in ``FFA`` and ``Experimental`` mode.

    """
    def parse(self):
        """Unpacks the data."""
        self.players = []
        for _ in range(self.getUint32()):
            self.players.append(Player(id=self.getUint32(),
                                       name=self.string()))

    def __repr__(self):
        return repr(self.players)


class TeamsScore(BaseMSG):
    """
    The ``TeamScore``.

    The percent of mass of each team.

    This message is only received in the ``Team`` mode.

    """
    def parse(self):
        """Unpacks the data."""
        self.numteams = self.getUint32()
        self.players = [self.getFloat32() for i in range(self.numteams)]

    def __repr__(self):
        return repr(self.players)


class ScreenAndCamera(BaseMSG):
    """
    Screen and Camera position, all in one.

    This message is the first message in the stream.

    """
    def parse(self):
        """Unpacks the data."""
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
    """
    Change in the camera position and/or the zoom.

    Only received in ``Spectate`` mode.

    """
    def parse(self):
        """Unpacks the data."""
        self.camera = Camera(x=self.getFloat32(),
                             y=self.getFloat32(),
                             zoom=self.getFloat32())

    def __repr__(self):
        return repr(self.camera)


class PlayerCell(BaseMSG):
    """
    ID of the player.

    """
    def parse(self):
        """Unpacks the data."""
        self.cell = PlayerID(self.getUint32())

    def __repr__(self):
        return repr(self.cell)


class ResetSomething(BaseMSG):
    """
    This message is present in the code but never seen.

    """
    def parse(self):
        """Unpacks the data."""
        pass


class SetQARA(BaseMSG):
    """
    This message is present in the code but never seen.

    """
    def parse(self):
        """Unpacks the data."""
        self.ca = self.getInt16()
        self.da = self.getInt16()
        self.sa = True


class MSGType(Enum):
    """
    This enum contains the identifier of each message along with the
    name of the class which parses it.

    """
    Status = 16
    CameraPosition = 17
    ResetSomething = 20
    SetQARA = 21
    PlayerCell = 32
    Leaderboard = 49
    TeamsScore = 50
    ScreenAndCamera = 64

    @property
    def cls(self):
        """Returns the parser class of this enum."""
        return globals().get(self.name)


class MSG(BaseMSG):
    """
    All messages.

    This class identify the specific message type and calls the proper
    parser.

    """
    def parse(self):
        """Unpacks the message identifier and instantiate the parser."""
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
