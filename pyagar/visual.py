"""
``pyagar.visual``
=================

Provides the default visualizer.

"""
# pylint: disable=C0103
import asyncio
import ctypes
import math
import os
import time
import warnings

try:
    from sdl2 import sdlgfx
    from sdl2 import sdlttf
    import sdl2
    import sdl2.ext
except ImportError:
    warnings.warn("Can't import pysdl2. The visualizer is not available.")

from pyagar.log import logger
from pyagar.messages import Camera
from pyagar.messages import Status
from pyagar.messages import ScreenAndCamera
from pyagar.messages import CameraPosition
from pyagar.messages import PlayerCell
from pyagar.messages import Leaderboard

FRAME_RATE = 60

HERE = os.path.realpath(os.path.dirname(__file__))

FONT_PATH = os.path.join(HERE, 'static', 'Ubuntu-R.ttf')


class SDLError(Exception):
    pass


def asrt(code):
    """
    If there is an error on a SDL call raise an exception with the error
    description.

    """
    if isinstance(code, int):
        if code != 0:
            raise SDLError(sdl2.SDL_GetError())
        else:
            return code
    elif hasattr(code, 'contents'):
        try:
            code.contents
        except ValueError as exc:
            raise SDLError(exc)
        else:
            return code
    else:
        return code


class Visualizer:
    """
    SDL based visualizer.

    """
    def __init__(self, client, view_only=False, hardware=True):
        self.names = dict()
        self.messages = asyncio.Queue()
        self.client = client
        self.view_only = view_only
        self.players = dict()
        self.player_id = None

        self.renderer = None
        if hardware:
            self.renderer_flags = sdl2.SDL_RENDERER_ACCELERATED
        else:
            self.renderer_flags = sdl2.SDL_RENDERER_SOFTWARE

        self.mouse_x = self.mouse_y = None
        self.move = None
        self.last_move = None

        self.now = self.last = self.last_move_send = time.monotonic()

        self.window_w = None
        self.window_h = None
        self.ref_rate = None

        self.stage_w = None
        self.stage_h = None

        #: The game board information sent by the server.
        self._gamescreen = None
        self.gamescreen_w = None
        self.gamescreen_h = None

        #: The texture we draw to.
        self.stage = None

        #: The window where we show the game.
        self.window = None

        self._camera = None

        self.fullscreen = False
        self.user_zoom = 0
        self.pixel_format = None
        self.font = {}

        self.renderer_info = sdl2.SDL_RendererInfo()

        self.leaderboard = None

    def update_leaderboard(self, data):
        lines = []

        max_width = ctypes.c_int(0)
        total_height = 0

        def write_line(msg, size):
            nonlocal max_width
            nonlocal total_height
            surface = asrt(sdlttf.TTF_RenderUTF8_Blended(
                self.font[size],
                msg.encode('utf-8'),
                sdl2.SDL_Color(255, 255, 255, 255)))

            texture = asrt(sdl2.SDL_CreateTextureFromSurface(
                self.renderer,
                surface))

            sdl2.SDL_FreeSurface(surface)
            lines.append(texture)

            # Update max_width.
            width = ctypes.c_int(0)
            height = ctypes.c_int(0)
            sdlttf.TTF_SizeUTF8(
                self.font[size],
                msg.encode('utf-8'),
                width,
                height)
            max_width = max(max_width, width, key=lambda c: c.value)
            total_height += height.value

        write_line("Leaderboard", 64)
        for idx, cell in enumerate(data.players):
            write_line(str(idx) + '. ' + cell.name, 32)

        if self.leaderboard is not None:
            sdl2.SDL_DestroyTexture(self.leaderboard)

        self.leaderboard = sdl2.SDL_CreateTexture(
            self.renderer,
            self.pixel_format,
            sdl2.SDL_TEXTUREACCESS_TARGET,
            max_width.value,
            total_height)

        sdl2.SDL_SetRenderTarget(self.renderer,
                                 self.leaderboard)
        sdl2.SDL_SetRenderDrawColor(self.renderer, 0, 0, 0, 128)
        sdl2.SDL_RenderClear(self.renderer)

        # Copy all strings to the leaderboard's texture.
        h = ctypes.c_int(0)
        w = ctypes.c_int(0)
        offset_height = 0
        for line in lines:
            asrt(sdl2.SDL_QueryTexture(line, None, None, w, h))
            asrt(sdl2.SDL_RenderCopy(
                    self.renderer,
                    line,
                    None,
                    sdl2.SDL_Rect(0, offset_height, w.value, h.value)))
            offset_height += h.value
            sdl2.SDL_DestroyTexture(line)

        sdl2.SDL_SetTextureBlendMode(
            self.leaderboard,
            sdl2.SDL_BLENDMODE_BLEND)

    def get_capabilities(self):
        asrt(sdl2.SDL_GetRendererInfo(self.renderer, self.renderer_info))
        logger.debug("Renderer max texture size: %dx%d",
                     self.renderer_info.max_texture_width,
                     self.renderer_info.max_texture_height)
        flags = "|".join(filter(None,
            (('SDL_RENDERER_SOFTWARE'
              if sdl2.SDL_RENDERER_SOFTWARE & self.renderer_info.flags
              else ''),
             ('SDL_RENDERER_ACCELERATED'
              if sdl2.SDL_RENDERER_ACCELERATED & self.renderer_info.flags
              else ''),
             ('SDL_RENDERER_PRESENTVSYNC'
              if sdl2.SDL_RENDERER_PRESENTVSYNC & self.renderer_info.flags
              else ''),
             ('SDL_RENDERER_TARGETTEXTURE'
              if sdl2.SDL_RENDERER_TARGETTEXTURE & self.renderer_info.flags
              else ''))))
        logger.debug("Renderer capabilities: %s", flags)

    def tr_game2stage_coords(self, x, y):
        """Translate from game cords to stage coordinates."""
        if self.gamescreen is None:
            raise ValueError("Screen is not setted.")
        else:
            s_x = self.remap(x,
                             self.gamescreen.x1,
                             self.gamescreen.x2,
                             0,
                             self.stage_w)
            s_y = self.remap(y,
                             self.gamescreen.y1,
                             self.gamescreen.y2,
                             0,
                             self.stage_h)
            return int(s_x), int(s_y)

    def tr_game2stage_size(self, size):
        """Translate a size (in pixels) from game to stage."""
        if self.gamescreen is None:
            raise ValueError("Screen is not setted.")
        else:
            size = size ** 2
            gs_area = ((self.gamescreen.x2 - self.gamescreen.x1) * 
                       (self.gamescreen.y2 - self.gamescreen.y1))
            st_area = self.stage_w * self.stage_h

            return int(math.sqrt(st_area * size / gs_area))


    @staticmethod
    def remap(o_val, o_min, o_max, n_min, n_max):
        """Map a value from one range to another."""
        o_range = (o_max - o_min)  
        n_range = (n_max - n_min)  
        n_value = (((o_val - o_min) * n_range) / o_range) + n_min
        return n_value

    def tr_win2game_coords(self, x, y):
        """Translate from window coords to game coordinates."""
        cell = self.players.get(self.player_id)
        if cell is None:
            return None
        else:
            camera = self.camera_rect

            # Camera rect
            c_x1 = camera.x
            c_x2 = camera.x + camera.w
            c_y1 = camera.y
            c_y2 = camera.y + camera.h

            # Window rect
            w_x1 = 0
            w_x2 = self.window_w
            w_y1 = 0
            w_y2 = self.window_h

            on_camera_x = self.remap(x, w_x1, w_x2, c_x1, c_x2)
            on_camera_y = self.remap(y, w_y1, w_y2, c_y1, c_y2)

            m_x = int(self.remap(on_camera_x,
                                 0,
                                 self.stage_w,
                                 self.gamescreen.x1,
                                 self.gamescreen.x2))
            m_y = int(self.remap(on_camera_y,
                                 0,
                                 self.stage_h,
                                 self.gamescreen.y1,
                                 self.gamescreen.y2))

            return m_x, m_y

    @property
    def gamescreen(self):
        return self._gamescreen

    @gamescreen.setter
    def gamescreen(self, value):
        self._gamescreen = value

        self.gamescreen_w = int(value.x2 - value.x1)
        if self.gamescreen_w > self.renderer_info.max_texture_width:
            self.stage_w = self.renderer_info.max_texture_width
        else:
            self.stage_w = self.gamescreen_w

        self.gamescreen_h = int(value.y2 - value.y1)
        if self.gamescreen_h > self.renderer_info.max_texture_height:
            self.stage_h = self.renderer_info.max_texture_height
        else:
            self.stage_h = self.gamescreen_h

        if self.stage is not None:
            sdl2.SDL_DestroyTexture(self.stage)
        self.stage = sdl2.SDL_CreateTexture(
            self.renderer,
            self.pixel_format,
            sdl2.SDL_TEXTUREACCESS_TARGET,
            self.stage_w,
            self.stage_h)

    @property
    def camera(self):
        return self._camera

    @camera.setter
    def camera(self, value):
        self._camera = value

    @property
    def camera_rect(self):
        x, y = self.tr_game2stage_coords(self.camera.x, self.camera.y)

        zoom = self.camera.zoom + self.user_zoom / 1000

        w = int(self.stage_w * zoom)
        h = int(self.stage_h * zoom)

        w = int(w * self.window_w / self.window_h)

        x = int(x - w / 2)
        y = int(y - h / 2)

        if x + w > self.stage_w:
            x = self.stage_w - w
        if y + h > self.stage_h:
            y = self.stage_h - h
        if x < 0:
            x = 0
        if y < 0:
            y = 0

        return sdl2.SDL_Rect(x, y, w, h)

    @staticmethod
    def hex2color(h):
        i = int(h, base=16)
        return sdl2.SDL_Color((i & 0xff0000) >> 16,
                              (i & 0x00ff00) >> 8,
                              (i & 0x0000ff),
                              255)

    def get_font(self, size):
        size = size / 4
        best = min(self.font.keys(), key=lambda x: abs(size-x))
        return self.font[best]

    def refresh(self):
        """
        Draw the current status of the game in ``window``.

        The overall process is:

          1. The server send information about the board size and status.

          1.1. We keep the information about the board in ``gamescreen``.

          2. We draw the game in the texture ``stage``. This texture can
             be smaller than ``gamescreen``.

          3. The rectangle ``camera`` (in game coordinates) is copied from
             ``stage`` to ``window``.

        """
        main = self.players.get(self.player_id)
        if main:
            self.camera = Camera(main.x, main.y, 0.085)

        camera = self.camera_rect

        # Set background
        sdl2.SDL_SetRenderTarget(self.renderer,
                                 self.stage)
        sdl2.SDL_SetRenderDrawColor(self.renderer, 0, 0, 0, 255)
        sdl2.SDL_RenderClear(self.renderer)

        # Draw the cells (Viruses last)
        cells = sorted(self.players.values(),
                       key=lambda c: (int(c.is_virus), c.size))
        for cell in cells:
            if cell.id == self.player_id:
                if self.client is not None:
                    label = self.client.nick
                else:
                    label = "PLAYER"
            else:
                label = self.names.get(cell.id)

            x, y = self.tr_game2stage_coords(cell.x, cell.y)
            size = self.tr_game2stage_size(cell.size)

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

            if cell.is_virus:
                border_size = int(size / 5)
            else:
                border_size = int(size / 25)

            # Cell border
            sdlgfx.filledCircleColor(self.renderer, x, y,
                                     size,
                                     border_color)

            # Cell fill
            sdlgfx.filledCircleColor(self.renderer, x, y,
                                     size - border_size,
                                     fill_color)
            if label:
                try:
                    text = asrt(sdlttf.TTF_RenderUTF8_Blended(
                        self.get_font(size),
                        label.encode('utf-8', errors='ignore'),
                        sdl2.SDL_Color(255, 255, 255, 255),
                        ))

                    text_texture = asrt(sdl2.SDL_CreateTextureFromSurface(
                        self.renderer,
                        text))

                    asrt(sdl2.SDL_FreeSurface(text.contents))
                    asrt(sdl2.SDL_RenderCopy(
                            self.renderer,
                            text_texture,
                            None,
                            sdl2.SDL_Rect(int(x-size*0.75),
                                          int(y-size*0.50),
                                          int(size*1.5),
                                          int(size))))
                    asrt(sdl2.SDL_DestroyTexture(text_texture))
                except SDLError:
                    logger.exception("Error labeling cell.")


        # Set background in window
        sdl2.SDL_SetRenderTarget(self.renderer, None)
        sdl2.SDL_SetRenderDrawColor(self.renderer, 0, 0, 0, 255)
        sdl2.SDL_RenderClear(self.renderer)

        # Copy the stage
        sdl2.SDL_RenderCopy(self.renderer,
                            self.stage,
                            camera,
                            sdl2.SDL_Rect(0, 0, self.window_w, self.window_h))

        if self.leaderboard is not None:
            sdl2.SDL_RenderCopy(
                self.renderer,
                self.leaderboard,
                None,
                sdl2.SDL_Rect(
                    int(self.window_w * 5 / 6),
                    0,
                    int(self.window_w / 6),
                    int(self.window_h * 2 / 3)))

        # Refresh
        sdl2.SDL_RenderPresent(self.renderer)


    def get_screen_size(self):
        display = sdl2.SDL_DisplayMode()
        ref_rate = FRAME_RATE
        size = None
        for idx in range(sdl2.SDL_GetNumVideoDisplays()):
            res = sdl2.SDL_GetCurrentDisplayMode(idx, display)
            if res == 0:
                if size:
                    size = min(display.w, display.h, size)
                else:
                    size = min(display.w, display.h)
                ref_rate = min(ref_rate, display.refresh_rate)

        if size and ref_rate:
            self.window_w = self.window_h = int(size * 0.8)
            self.ref_rate = ref_rate
        else:
            print("Error getting display mode.")

    def create_window(self):
        if self.renderer is not None:
            sdl2.SDL_DestroyRenderer(self.renderer)
        if self.window is not None:
            sdl2.SDL_DestroyWindow(self.window.window)

        self.window = sdl2.ext.Window(
            "pyagar",
            size=(self.window_w, self.window_h),
            flags=sdl2.SDL_WINDOW_RESIZABLE)

        self.window.show()
        self.renderer = sdl2.SDL_CreateRenderer(
            self.window.window,
            -1,
            self.renderer_flags)
        self.get_capabilities()

        display = sdl2.SDL_DisplayMode()
        sdl2.SDL_GetWindowDisplayMode(self.window.window,
                                      display)
        self.pixel_format = display.format

        if self._gamescreen is not None:
            self.gamescreen = self._gamescreen

    def toggle_fullscreen(self):
        if self.fullscreen:
            logger.debug("Fullscreen OFF")
            self.create_window()
            sdl2.SDL_SetWindowSize(self.window.window,
                                   self.window_w,
                                   self.window_h)
            self.fullscreen = False
        else:
            logger.debug("Fullscreen ON")
            sdl2.SDL_SetWindowFullscreen(
                self.window.window,
                sdl2.SDL_WINDOW_FULLSCREEN)
            self.fullscreen = True

    @asyncio.coroutine
    def run(self):
        sdl2.ext.init()
        sdlttf.TTF_Init()
        self.get_screen_size()

        for i in range(5, 10):
            size = 2**i
            self.font[size] = sdlttf.TTF_OpenFont(
                FONT_PATH.encode('ascii'),
                size)

        self.last = time.monotonic()

        self.create_window()

        # Window creation, we wait for a ScreenAndCamera message.
        while True:
            data = yield from self.messages.get()
            if isinstance(data, ScreenAndCamera):
                self.gamescreen = data.screen
                self.camera = Camera(data.camera.x, data.camera.y, 0.085)
                break

        # Play
        while True:
            try:
                data = yield from asyncio.wait_for(self.messages.get(),
                                                   1 / self.ref_rate)
            except asyncio.TimeoutError:
                data = None

            if isinstance(data, PlayerCell):
                self.player_id = data.cell.id
            elif isinstance(data, CameraPosition):
                self.camera = data.camera
            elif isinstance(data, Leaderboard):
                self.update_leaderboard(data)
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
                        self.window_w = event.window.data1
                        self.window_h = event.window.data2
                        logger.debug("Window resized %dx%d",
                                     event.window.data1,
                                     event.window.data2)
                elif event.type == sdl2.SDL_KEYDOWN:
                    if event.key.keysym.sym == sdl2.SDLK_f:
                        self.toggle_fullscreen()
                    elif event.key.keysym.sym == sdl2.SDLK_ESCAPE:
                        if self.fullscreen:
                            self.toggle_fullscreen()
                        else:
                            logger.debug("User pressed ESC, exiting.")
                            return
                elif event.type == sdl2.SDL_MOUSEWHEEL:
                    self.user_zoom += event.wheel.y
                    if self.user_zoom > 50:
                        self.user_zoom = 50
                    elif self.user_zoom < -50:
                        self.user_zoom = -50
                    else:
                        logger.debug("UserZoom: %r", self.user_zoom)
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
                        self.move = self.tr_win2game_coords(self.mouse_x,
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
                    self.move = self.tr_win2game_coords(self.mouse_x,
                                                        self.mouse_y)
                    if self.move:
                        asyncio.async(self.client.move(*self.move))
                        self.last_move = self.move
                        self.last_move_send = self.now

            delay = abs(self.last - self.now)
            if self.messages.empty() and delay > 1 / self.ref_rate:
                self.refresh()
                self.last = self.now
