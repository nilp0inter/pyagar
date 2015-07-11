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

from pyagar.log import logger
from pyagar.messages import Cell, Camera
from pyagar.messages import Status, ScreenAndCamera, CameraPosition, PlayerCell

FRAME_RATE = 60

BLACK = sdl2.ext.Color(0, 0, 0)
WHITE = sdl2.ext.Color(255, 255, 255)

HERE = os.path.realpath(os.path.dirname(__file__))

FONT_PATH = os.path.join(HERE, 'static', 'Ubuntu-R.ttf')


class Visualizer:

    factory = sdl2.ext.SpriteFactory(sdl2.ext.SOFTWARE)

    def __init__(self, client, view_only=False, hardware=True):
        self.names = dict()
        self.messages = asyncio.Queue()
        self.client = client
        self.view_only = view_only
        self.players = dict()
        self.player_id = None

        if hardware:
            self.renderer_flags = sdl2.SDL_RENDERER_ACCELERATED
        else:
            self.renderer_flags = sdl2.SDL_RENDERER_SOFTWARE

        self.window = None
        self.winsurface = None

        self.mouse_x = self.mouse_y = None
        self.move = None
        self.last_move = None

        self.last = self.last_move_send = time.monotonic()

        self.s_width = None
        self.s_height = None
        self.s_refresh = None

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

        if self.stage is not None:
            sdl2.SDL_DestroyTexture(self.stage)
        self.stage = sdl2.SDL_CreateTexture(
            self.renderer,
            self.pixel_format,
            sdl2.SDL_TEXTUREACCESS_TARGET,
            self.width,
            self.height)

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

        w = int(w * self.s_width / self.s_height)
        
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

    def get_font(self, size):
        size = size / 4
        best = min(self.font.keys(), key=lambda x: abs(size-x))
        return self.font[best]

    def refresh(self):
        main = self.players.get(self.player_id)
        if main:
            self.camera = Camera(main.x, main.y, 0.085)

        camera = self.camera_rect

        # Set background
        sdl2.SDL_SetRenderTarget(self.renderer,
                                 self.stage)
        sdl2.SDL_SetRenderDrawColor(self.renderer, 0, 0, 0, 255);
        sdl2.SDL_RenderClear(self.renderer)

        # Draw the cells (Viruses last)
        cells = sorted(self.players.values(),
                       key=lambda c: (int(c.is_virus), c.size))
        for cell in cells:
            if cell.id == self.player_id:
                label = self.client.nick
            else:
                label = self.names.get(cell.id)

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
                    self.get_font(cell.size),
                    label.encode('utf-8', errors='ignore'),
                    sdl2.SDL_Color(255, 255, 255, 255),
                    self.hex2SDLcolor(cell.color))

                try:
                    text.contents
                except ValueError:
                    pass
                else:
                    text_texture = sdl2.SDL_CreateTextureFromSurface(
                        self.renderer,
                        text)
                    sdl2.SDL_FreeSurface(text.contents)
                    sdl2.SDL_RenderCopy(
                        self.renderer,
                        text_texture,
                        None,
                        sdl2.SDL_Rect(int(x-cell.size*0.75),
                                      int(y-cell.size*0.50),
                                      int(cell.size*1.5),
                                      int(cell.size)))
                    sdl2.SDL_DestroyTexture(text_texture)


        # Set background in window
        sdl2.SDL_SetRenderTarget(self.renderer, None)
        sdl2.SDL_SetRenderDrawColor(self.renderer, 0, 0, 0, 255);
        sdl2.SDL_RenderClear(self.renderer)

        # Copy the stage
        sdl2.SDL_RenderCopy(self.renderer,
                            self.stage,
                            camera,
                            sdl2.SDL_Rect(0, 0, self.s_width, self.s_height))

        # Refresh
        sdl2.SDL_RenderPresent(self.renderer)


    def get_screen_size(self):
        display = sdl2.SDL_DisplayMode()
        refresh = FRAME_RATE
        size = None
        for idx in range(sdl2.SDL_GetNumVideoDisplays()):
            res = sdl2.SDL_GetCurrentDisplayMode(idx, display)
            if res == 0:
                if size:
                    size = min(display.w, display.h, size)
                else:
                    size = min(display.w, display.h)
                refresh = min(refresh, display.refresh_rate)

        if size and refresh:
            self.s_width = self.s_height = int(size * 0.8)
            self.s_refresh = refresh
        else:
            print("Error getting display mode.")

    @asyncio.coroutine
    def run(self):
        sdl2.ext.init()
        sdlttf.TTF_Init()
        self.get_screen_size()

        self.font = {}
        for i in range(5, 10):
            size = 2**i
            self.font[size] = sdlttf.TTF_OpenFont(
                FONT_PATH.encode('ascii'),
                size)

        self.last = time.monotonic()

        self.window = sdl2.ext.Window(
            "pyagar",
            size=(self.s_width, self.s_height),
            flags=sdl2.SDL_WINDOW_RESIZABLE)

        self.window.show()
        self.renderer = sdl2.SDL_CreateRenderer(
            self.window.window,
            -1, 
            self.renderer_flags)

        display = sdl2.SDL_DisplayMode()
        sdl2.SDL_GetWindowDisplayMode(self.window.window,
                                  display)
        self.pixel_format = display.format

        # Window creation, we wait for a ScreenAndCamera message.
        while True:
            data = yield from self.messages.get()
            if isinstance(data, ScreenAndCamera):
                self.screen = data.screen
                self.camera = Camera(data.camera.x, data.camera.y, 0.085)
                break

        # Play
        while True:
            try:
                data = yield from asyncio.wait_for(self.messages.get(),
                                                   1 / self.s_refresh)
            except asyncio.TimeoutError:
                data = None

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
                    logger.debug("QUIT event received.")
                    return
                elif event.type == sdl2.SDL_WINDOWEVENT:
                    if event.window.event == sdl2.SDL_WINDOWEVENT_RESIZED:
                        self.s_width = event.window.data1
                        self.s_height = event.window.data2
                        logger.info("Window resized %dx%d",
                                    event.window.data1,
                                    event.window.data2)
                if not self.view_only:
                    if event.type == sdl2.SDL_KEYDOWN:
                        if event.key.keysym.sym == sdl2.SDLK_SPACE:
                            logger.debug("SPACE key pressed.")
                            asyncio.async(self.client.split())
                        elif event.key.keysym.sym == sdl2.SDLK_w:
                            logger.debug("W key pressed.")
                            asyncio.async(self.client.eject())
                    elif event.type == sdl2.SDL_MOUSEMOTION:
                        self.mouse_x = event.motion.x
                        self.mouse_y = event.motion.y
                        self.move = self.mouse_to_stage_coords(self.mouse_x,
                                                               self.mouse_y)
                    elif (event.type == sdl2.SDL_MOUSEBUTTONDOWN and
                          event.button.button == sdl2.SDL_BUTTON_LEFT):
                        logger.debug("Mouse button pressed.")
                        asyncio.async(self.client.spawn())
                        
            self.now = time.monotonic()

            if self.move is not None:
                if self.move != self.last_move:
                    asyncio.async(self.client.move(*self.move))
                    self.last_move = self.move
                    self.last_move_send = self.now
                elif self.now - self.last_move_send > 0.05:
                    self.move = self.mouse_to_stage_coords(self.mouse_x,
                                                           self.mouse_y)
                    if self.move:
                        asyncio.async(self.client.move(*self.move))
                        self.last_move = self.move
                        self.last_move_send = self.now

            delay = abs(self.last - self.now)
            if data is not None and delay > 1 / self.s_refresh:
                self.refresh()
                self.last = self.now
