from collections import namedtuple
import asyncio
import ctypes
import sys
import time
import traceback

from sdl2 import mouse
from sdl2 import video
import sdl2
import sdl2.ext

from pyagar.messages import Status, ScreenAndCamera, CameraPosition, PlayerCell
from pyagar.messages import Cell, Camera

FRAME_RATE = 60

BLACK = sdl2.ext.Color(0, 0, 0)
WHITE = sdl2.ext.Color(255, 255, 255)


class Visualizer:

    factory = sdl2.ext.SpriteFactory(sdl2.ext.SOFTWARE)

    def __init__(self, client, view_only=False):
        self.messages = asyncio.Queue()
        self.client = client
        self.view_only = view_only
        self.players = dict()
        self.last = None
        self.player_id = None

        self.window = None
        self.winsurface = None

        self.mouse_x = ctypes.c_int()
        self.mouse_y = ctypes.c_int()

        self.s_width = 1024
        self.s_height = 1024

        self.width = None
        self.height = None

        self.stage = None

        self._screen = None
        self._camera = None

    def to_coords(self, x, y):
        if self.screen is None:
            raise ValueError("Screen not setted.")
        else:
            x_offset = 0 - self.screen.x1
            y_offset = 0 - self.screen.y1

            return int(x + x_offset), int(y + y_offset)

    def mouse_to_stage_coords(self, x, y):
        cell = self.players.get(self.player_id)
        if cell is None:
            return None
        else:
            m_x = cell.x + (x - self.s_width / 2)
            m_y = cell.y + (y - self.s_height / 2)
            
            return m_x, m_y

    @property
    def screen(self):
        return self._screen

    @screen.setter
    def screen(self, value):
        self._screen = value
        self.width = int(value.x2 - value.x1)
        self.height = int(value.y2 - value.y1)
        self.stage = sdl2.surface.SDL_CreateRGBSurface(
            0,
            self.width,
            self.height,
            32, 0, 0, 0, 0)

    @property
    def camera(self):
        return self._camera

    @camera.setter
    def camera(self, value):
        self._camera = value

    @property
    def camera_rect(self):
        x, y = self.to_coords(self.camera.x, self.camera.y)
        w = int(self.width * self.camera.zoom)
        h = int(self.height * self.camera.zoom)

        x = int(x - w / 2)
        y = int(y - h / 2)

        if x + w > self.width:
            x = self.width - w
        if y + h > self.height:
            y = self.height - h
        if x < 0:
            x = 0
        if y < 0:
            y = 0

        return sdl2.SDL_Rect(x, y, w, h)

    @staticmethod
    def hex2color(h):
        i = int(h, base=16)
        return sdl2.ext.Color((i & 0xff0000) >> 16,
                              (i & 0x00ff00) >> 8,
                              (i & 0x0000ff))

    def refresh(self):
        # Set background
        res = sdl2.surface.SDL_FillRect(
            self.stage.contents,
            self.camera_rect,
            sdl2.ext.prepare_color(BLACK, self.stage.contents))

        # Draw the cells
        for cell in self.players.values():
            if cell.id == self.player_id:
                color = WHITE
                self.camera = Camera(cell.x, cell.y, 0.125)
            else:
                color = self.hex2color(cell.color)
            color = sdl2.ext.prepare_color(color, self.stage.contents)
            x, y = self.to_coords(cell.x, cell.y)
            w = h = int(cell.size * 1.5)
            x = int(x - w / 2)
            y = int(y - h / 2)
            sdl2.surface.SDL_FillRect(self.stage.contents,
                                      sdl2.SDL_Rect(x, y, w, h),
                                      color)
        
        # Copy to the screen
        sc_rect = sdl2.SDL_Rect(0, 0, self.s_width, self.s_height)
        res = sdl2.surface.SDL_BlitScaled(self.stage.contents,
                                          self.camera_rect,
                                          self.winsurface,
                                          sc_rect)

        # Refresh the window
        self.window.refresh()
                                     

    @asyncio.coroutine
    def run(self):
        sdl2.ext.init()
        self.last = time.monotonic()

        self.window = sdl2.ext.Window("agar.io", size=(self.s_width,
                                                       self.s_height))
        self.window.show()
        self.winsurface = self.window.get_surface()

        # Window creation, we wait for a ScreenAndCamera message.
        while True:
            data = yield from self.messages.get()
            if isinstance(data, ScreenAndCamera):
                self.screen = data.screen
                self.camera = data.camera
                break

        # Play
        while True:
            data = yield from self.messages.get()

            if isinstance(data, PlayerCell):
                self.player_id = data.cell.id
            elif isinstance(data, CameraPosition):
                self.camera = data.camera
            elif isinstance(data, Status):
                for cell in data.cells:
                    self.players[cell.id] = cell
                for cell in data.dissapears:
                    if cell.id in self.players:
                        del self.players[cell.id]
                for eats in data.eat:
                    if eats.eatee == self.player_id:
                        self.player_id = None
                    if eats.eatee in self.players:
                        del self.players[eats.eatee]

            self.now = time.monotonic()
            delay = abs(self.last - self.now)
            if delay > 1 / FRAME_RATE:
                # Read sdl events
                for event in sdl2.ext.get_events():
                    if event.type == sdl2.SDL_QUIT:
                        sys.exit(0)

                self.refresh()

                if not self.view_only:
                    buttons = mouse.SDL_GetMouseState(self.mouse_x,
                                                      self.mouse_y)
                    if buttons == 1:
                        yield from self.client.spawn()

                    move = self.mouse_to_stage_coords(self.mouse_x.value,
                                                      self.mouse_y.value)
                    if move is not None:
                        x, y = move
                        yield from self.client.move(x, y)

                self.last = self.now
