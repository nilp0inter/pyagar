from collections import namedtuple
import os
import asyncio
import ctypes
import sys
import time
import traceback

from sdl2 import mouse
from sdl2 import sdlgfx
from sdl2 import sdlttf
from sdl2 import video
import sdl2
import sdl2.ext

from pyagar.messages import Status, ScreenAndCamera, CameraPosition, PlayerCell
from pyagar.messages import Cell, Camera

FRAME_RATE = 60

BLACK = sdl2.ext.Color(0, 0, 0)
WHITE = sdl2.ext.Color(255, 255, 255)

HERE = os.path.realpath(os.path.dirname(__file__))

FONT_PATH = os.path.join(HERE, 'static', 'Ubuntu-R.ttf')


class Visualizer:

    factory = sdl2.ext.SpriteFactory(sdl2.ext.SOFTWARE)

    def __init__(self, client, view_only=False):
        self.names = dict()
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
            32,
            0,
            0,
            0,
            0)
        self.renderer = sdl2.SDL_CreateSoftwareRenderer(self.stage)

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

    @property
    def camera_border_rect(self):
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

        return sdl2.SDL_Rect(x-w, y-h, w*2, h*2)

    @staticmethod
    def hex2SDLcolor(h):
        i = int(h, base=16)
        return sdl2.SDL_Color((i & 0xff0000) >> 16,
                              (i & 0x00ff00) >> 8,
                              (i & 0x0000ff),
                              255)
    @staticmethod
    def hex2color(h):
        i = int(h, base=16)
        return sdl2.ext.Color((i & 0xff0000) >> 16,
                              (i & 0x00ff00) >> 8,
                              (i & 0x0000ff))

    def refresh(self):
        main = self.players.get(self.player_id)
        if main:
            self.camera = Camera(main.x, main.y, 0.085)

        camera = self.camera_rect

        # Set background
        sdl2.surface.SDL_FillRect(
            self.stage.contents,
            camera,
            sdl2.ext.prepare_color(BLACK, self.stage.contents))

        # Draw the cells (Viruses last)
        cells = sorted(self.players.values(),
                       key=lambda c: c.is_virus)
        for cell in cells:
            if cell.id == self.player_id:
                label = self.client.nick
            else:
                label = self.names.get(cell.id)

            color = sdl2.ext.prepare_color(self.hex2color(cell.color),
                                           self.stage.contents)

            x, y = self.to_coords(cell.x, cell.y)

            # Cell border
            fill_color = int('ff' + cell.color, base=16)

            r = int(cell.color[:2], base=16)
            g = int(cell.color[2:4], base=16)
            b = int(cell.color[4:], base=16)
            border_color = int('ff%0.2x%0.2x%0.2x' % 
                               (r - 0x10 if r > 0x10 else 0,
                                g - 0x10 if g > 0x10 else 0,
                                b - 0x10 if b > 0x10 else 0),
                               base=16)

            border_size = int((cell.size * 2) / 100)

            # Cell border
            sdlgfx.filledCircleColor(self.renderer, x, y,
                                     cell.size + border_size,
                                     border_color)

            # Cell fill
            sdlgfx.filledCircleColor(self.renderer, x, y, cell.size,
                                     fill_color)
            if label:
                text = sdlttf.TTF_RenderUTF8_Solid(
                    self.font,
                    label.encode('utf-8', errors='ignore'),
                    sdl2.SDL_Color(255, 255, 255, 255),
                    self.hex2SDLcolor(cell.color))

                text = sdl2.surface.SDL_ConvertSurface(
                    text.contents,
                    self.stage.contents.format,
                    0)

                sdl2.surface.SDL_BlitScaled(
                    text,
                    text.contents.clip_rect,
                    self.stage.contents,
                    sdl2.SDL_Rect(int(x-cell.size*0.75), int(y-cell.size*0.50),
                                  int(cell.size*1.5), int(cell.size)))

        sc_rect = sdl2.SDL_Rect(0, 0, self.s_width, self.s_height)

        # Copy to the screen
        sdl2.surface.SDL_BlitScaled(self.stage.contents,
                                    camera,
                                    self.winsurface,
                                    sc_rect)

        # Refresh the window
        self.window.refresh()

    @asyncio.coroutine
    def run(self):
        sdl2.ext.init()
        sdlttf.TTF_Init()
        self.font = sdlttf.TTF_OpenFont(FONT_PATH.encode('ascii'), 256)
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

                self.camera = Camera(data.camera.x, data.camera.y, 0.085)
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
                    if cell.name:
                        self.names[cell.id] = cell.name
                for cell in data.dissapears:
                    if cell.id in self.players:
                        del self.players[cell.id]
                for eats in data.eat:
                    if eats.eatee == self.player_id:
                        self.player_id = None
                    if eats.eatee in self.players:
                        del self.players[eats.eatee]

            # Read sdl events
            for event in sdl2.ext.get_events():
                if event.type == sdl2.SDL_QUIT:
                    sys.exit(0)
                if not self.view_only:
                    if event.type == sdl2.SDL_KEYDOWN:
                        if event.key.keysym.sym == sdl2.SDLK_SPACE:
                            asyncio.async(self.client.split())
                        elif event.key.keysym.sym == sdl2.SDLK_w:
                            asyncio.async(self.client.eject())
                    elif event.type == sdl2.SDL_MOUSEMOTION:
                        move = self.mouse_to_stage_coords(event.motion.x,
                                                          event.motion.y)
                        if move:
                            x, y = move
                            asyncio.async(self.client.move(x, y))
                    elif (event.type == sdl2.SDL_MOUSEBUTTONDOWN and
                          event.button.button == sdl2.SDL_BUTTON_LEFT):
                        asyncio.async(self.client.spawn())
                        
            self.now = time.monotonic()
            delay = abs(self.last - self.now)
            if delay > 1 / FRAME_RATE:
                self.refresh()
                self.last = self.now
