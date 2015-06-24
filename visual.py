import asyncio
import ctypes
import sys
import time
import traceback

from sdl2 import mouse
from sdl2 import video
import sdl2
import sdl2.ext

from messages import Status, ScreenAndCamera, CameraPosition, PlayerCell

FRAME_RATE = 60

BLACK = sdl2.ext.Color(0, 0, 0)
WHITE = sdl2.ext.Color(255, 255, 255)


class SoftwareRenderer(sdl2.ext.SoftwareSpriteRenderSystem):
    def __init__(self, window):
        super().__init__(window)

    def render(self, components):
        sdl2.ext.fill(self.surface, WHITE)
        super().render(components)


class Cell(sdl2.ext.Entity):
    def __init__(self, world, sprite, posx=0, posy=0):
        self.sprite = sprite
        self.sprite.position = posx, posy


class Camera(sdl2.ext.Entity):
    def __init__(self, world, sprite, posx=0, posy=0):
        self.sprite = sprite
        self.sprite.position = posx, posy


class Visualizer:

    factory = sdl2.ext.SpriteFactory(sdl2.ext.SOFTWARE)

    def __init__(self, client, view_only=False):
        self.messages = asyncio.Queue()
        self.client = client
        self.view_only = view_only
        self.cells = dict()
        self.players = dict()
        self.running = True
        self.last = None
        self.player_id = None

        self.window = None
        self.world = None

        self.mouse_x = ctypes.c_int()
        self.mouse_y = ctypes.c_int()

        self.screen_width = self.screen_height = 1024

        self.camera_x = 0
        self.camera_y = 0
        self.camera_zoom = 1
        self.camera = None
        self.camera_sp = None

    @staticmethod
    def hex2color(h):
        i = int(h, base=16)
        return sdl2.ext.Color((i & 0xff0000) >> 16,
                              (i & 0x00ff00) >> 8,
                              (i & 0x0000ff))

    def delete_cell(self, cell_id):
        del self.cells[cell_id]
        player = self.players.pop(cell_id)
        player.delete()

    def update_cell(self, cell):
        if cell.id in self.cells:  # Existing cell
            sprite = self.cells[cell.id]
            if sprite.size[0] != cell.size:  # Is Modified
                self.delete_cell(cell.id)
            else:
                return

        if cell.id == self.player_id:
            color = WHITE
        else:
            color = self.hex2color(cell.color)

        width = height = int(cell.size / 10)
        x = int(cell.x / 10 - width / 2)
        y = int(cell.y / 10 - height / 2)

        sprite = self.factory.from_color(color, size=(width, height))
        sprite.depth = -cell.size
        self.cells[cell.id] = sprite
        self.players[cell.id] = Cell(self.world, sprite, x, y)

    def update_camera(self, camera):
        if self.camera is not None:
            self.camera.delete()
        width = int(self.screen_width * camera.zoom)
        height = int(self.screen_height * camera.zoom)

        self.camera_x = int(camera.x / 10 - width / 2)
        self.camera_y = int(camera.y / 10 - height / 2)
        self.camera_zoom = camera.zoom

        self.camera_sp = self.factory.from_color(
            BLACK, size = (width, height))
        self.camera_sp.depth = -65535
        self.camera = Camera(self.world, self.camera_sp,
                             self.camera_x, self.camera_y)

    def set_window(self, data):
        self.screen_width = int((data.screen.x2 - data.screen.x1) / 10)
        self.screen_height = int((data.screen.y2 - data.screen.y1) / 10)
        self.window = sdl2.ext.Window(
            "agar.io",
            size=(self.screen_width, self.screen_height))
        self.window.show()
        self.world = sdl2.ext.World()

        spriterenderer = SoftwareRenderer(self.window)
        self.world.add_system(spriterenderer)

        self.update_camera(data.camera)

    @asyncio.coroutine
    def run(self):
        sdl2.ext.init()
        self.last = time.monotonic()

        # Window creation, we wait for a ScreenAndCamera message.
        while True:
            data = yield from self.messages.get()
            if isinstance(data, ScreenAndCamera):
                self.set_window(data)
                break

        # Play
        while True:
            data = yield from self.messages.get()

            if isinstance(data, PlayerCell):
                self.player_id = data.cell.id
            elif isinstance(data, CameraPosition):
                self.update_camera(data.camera)
            elif isinstance(data, Status):
                for cell in data.cells:
                    self.update_cell(cell)
                for cell in data.dissapears:
                    if cell.id in self.cells:
                        self.delete_cell(cell.id)
                for eats in data.eat:
                    if eats.eatee == self.player_id:
                        self.player_id = None
                    if eats.eatee in self.cells:
                        self.delete_cell(eats.eatee)

            self.now = time.monotonic()
            delay = abs(self.last - self.now)
            if self.messages.empty() and delay > 1 / FRAME_RATE:

                # Read sdl events
                for event in sdl2.ext.get_events():
                    if event.type == sdl2.SDL_QUIT:
                        sys.exit(0)

                self.world.process()

                if not self.view_only:
                    buttons = mouse.SDL_GetMouseState(self.mouse_x,
                                                      self.mouse_y)
                    if buttons == 1:
                        yield from self.client.spawn()

                    X = self.mouse_x.value * 10
                    Y = self.mouse_y.value * 10

                    yield from self.client.move(X, Y)

                self.last = self.now
