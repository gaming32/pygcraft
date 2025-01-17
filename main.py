from __future__ import print_function, nested_scopes, division
import sys, os
import math, random, time, datetime
try:
    import _thread as thread
except ImportError:
    import thread
from collections import deque
from pyglet import image, options
from pyglet.gl import *
from pyglet.graphics import TextureGroup
from pyglet.window import key, mouse
options['audio'] = ('openal', 'pulse', 'directsound', 'silent')
from pyglet import media
import settings

TICKS_PER_SEC = 60
SECTOR_SIZE = 8
WALKING_SPEED = 5
RUNNING_SPEED = 9
FLYING_SPEED = 15
FLY_RUNNING_SPEED = 21
GRAVITY = 20.0
MAX_JUMP_HEIGHT = 1.125
JUMP_SPEED = math.sqrt(2 * GRAVITY * MAX_JUMP_HEIGHT)
TERMINAL_VELOCITY = 50
PLAYER_HEIGHT = 2

# sys.path.append('savers_and_loaders')

xrange = range
if hasattr(time, 'process_time'):
    timefunc = time.process_time
else:
    timefunc = time.clock
if sys.version_info[0] == 2:
    input = raw_input

def _lerp(l, u, r):
    return (r * u) + ((1 - r) * l)
def lerp(colL, colU, rate):
    r = _lerp(colL[0], colU[0], rate)
    g = _lerp(colL[1], colU[1], rate)
    b = _lerp(colL[2], colU[2], rate)
    return r, g, b

def cube_vertices(x, y, z, n):
    return [
        x-n,y+n,z-n, x-n,y+n,z+n, x+n,y+n,z+n, x+n,y+n,z-n,
        x-n,y-n,z-n, x+n,y-n,z-n, x+n,y-n,z+n, x-n,y-n,z+n,
        x-n,y-n,z-n, x-n,y-n,z+n, x-n,y+n,z+n, x-n,y+n,z-n,
        x+n,y-n,z+n, x+n,y-n,z-n, x+n,y+n,z-n, x+n,y+n,z+n,
        x-n,y-n,z+n, x+n,y-n,z+n, x+n,y+n,z+n, x-n,y+n,z+n,
        x+n,y-n,z-n, x-n,y-n,z-n, x-n,y+n,z-n, x+n,y+n,z-n,
    ]

def tex_coord(x, y, n=8):
    m = 1.0 / n
    dx = x * m
    dy = y * m
    return dx, dy, dx + m, dy, dx + m, dy + m, dx, dy + m

def tex_coords(top, bottom, side):
    top = tex_coord(*top)
    bottom = tex_coord(*bottom)
    side = tex_coord(*side)
    result = []
    result.extend(top)
    result.extend(bottom)
    result.extend(side * 4)
    return result

class Block:
    def __init__(self, texture, name, height=0, break_sfx=None):
        self.texture = texture
        self.name = name
        self.height = height
        if break_sfx is None:
            break_sfx = []
            for file in os.listdir('sounds'):
                if file.startswith('%s_break' % name.lower()):
                    break_sfx.append('sounds/%s' % file)
                    print(file)
        if settings.DO_BREAK_SFX:
            for (num, sound) in enumerate(break_sfx):
                break_sfx[num] = media.load(sound)
        else:
            self.break_sfx = None
    def notify_update(self, world, x, y, z): 
        print('Block Update:', str(world)[:25], x, y, z)
    def block_update(self, world, x, y, z):
        if not settings.DO_BLOCK_UPDATES: return
        for (nx, ny, nz) in ((0,0,1), (0,1,0), (1,0,0), (0,0,-1), (0,-1,0), (-1,0,0)):
            coords = (x + nx), (y + ny), (z + nz)
            if coords in world:
                world[coords].notify_update(world, *coords)
    def destroy(self, world, x, y, z):
        self.block_update(world, x, y, z)
        if self.break_sfx is not None:
            try:
                print(self.break_sfx)
                print(random.choice(self.break_sfx))
                random.choice(self.break_sfx).play()
            except media.exceptions.MediaException: pass

TEXTURE_PATH = 'textures/texture.png'
GRASS = Block(tex_coords((1, 0), (1, 0), (1, 0)), 'GRASS')
DIRT = Block(tex_coords((0, 1), (0, 1), (0, 1)), 'DIRT')
SAND = Block(tex_coords((1, 1), (1, 1), (1, 1)), 'SAND')
STONE = Block(tex_coords((2, 0), (2, 0), (2, 0)), 'STONE')
IRON = Block(tex_coords((2, 1), (2, 1), (2, 1)), 'IRON')
STEEL = Block(tex_coords((3, 1), (3, 1), (3, 1)), 'STEEL')
WOOD = Block(tex_coords((0, 0), (0, 0), (0, 0)), 'WOOD')
LOG = Block(tex_coords((3, 0), (3, 0), (3, 3)), 'LOG')
BENCH = Block(tex_coords((0, 2), (0, 0), (0, 0)), 'BENCH')
OVEN = Block(tex_coords((3, 2), (3, 2), (1, 2)), 'OVEN')
REACTOR = Block(tex_coords((2, 2), (2, 2), (2, 2)), 'REACTOR')
BLACK_IRON = Block(tex_coords((3, 2), (3, 2), (3, 2)), 'BLACK_IRON')
FIRE = Block(tex_coords((0, 4), (0, 4), (0, 3)), 'FIRE')
ICE = Block(tex_coords((1, 3), (1, 3), (1, 3)), 'ICE')
WATER = Block(tex_coords((2, 3), (2, 3), (2, 3)), 'WATER')
BLOCKS = [GRASS, DIRT, SAND, STONE, IRON, STEEL, WOOD, LOG, BENCH, OVEN, REACTOR, BLACK_IRON, FIRE, ICE, WATER]
HALFBLOCKS = []
for block in BLOCKS:
    HALFBLOCKS.append(Block(block.texture, block.name+'_HALF', height=0.5))
FACES = [
    ( 0, 1, 0),
    ( 0,-1, 0),
    (-1, 0, 0),
    ( 1, 0, 0),
    ( 0, 0, 1),
    ( 0, 0,-1),
]

def normalize(position):
    x, y, z = position
    x, y, z = (int(round(x)), int(round(y)), int(round(z)))
    return (x, y, z)

def sectorize(position):
    x, y, z = normalize(position)
    x, y, z = x // SECTOR_SIZE, y // SECTOR_SIZE, z // SECTOR_SIZE
    return (x, 0, z)

class Model(object):
    def __init__(self, world=None):
        self.batch = pyglet.graphics.Batch()
        self.group = TextureGroup(image.load(TEXTURE_PATH).get_texture())
        if world is None:
            world = {}
        self.world = world
        self.shown = {}
        self._shown = {}
        self.sectors = {}
        self.queue = deque()
        if not world:
            self._initialize()

    def _initialize(self, size=120, floor=GRASS, walls=IRON, hills=random.randint(40, 80), hillBlocks=[GRASS,SAND,STONE]):
        n = size
        s = 1
        y = 0
        def update_progress(progress, amount=1):
            progress += amount
            if settings.LOG_WORLD_GEN_PROGRESS:
                print('Generating World... Progress: %i/%i (%i%%)' % (progress, length, progress / length * 100), end='\r')
            return progress
        length = ((2 * size + 2) ** 2) + hills * 5000 - 483
        progress = 0
        for x in xrange(-n, n + 1, s):
            for z in xrange(-n, n + 1, s):
                self.add_block((x, y - 2, z), floor, immediate=False)
                self.add_block((x, y - 3, z), walls, immediate=False)
                if x in (-n, n) or z in (-n, n):
                    for dy in xrange(-2, 3):
                        self.add_block((x, y + dy, z), walls, immediate=False)
                progress = update_progress(progress)
        o = n - 20
        for _ in xrange(hills):
            a = random.randint(-o, o)
            b = random.randint(-o, o)
            c = -1
            h = random.randint(16, 35)
            s = random.randint(13, 29)
            d = 1
            t = random.choice(hillBlocks)
            for y in xrange(c, c + h):
                for x in xrange(a - s, a + s + 1):
                    for z in xrange(b - s, b + s + 1):
                        if (x - a) ** 2 + (z - b) ** 2 > (s + 1) ** 2:
                            continue
                        if (x - 0) ** 2 + (z - 0) ** 2 < 5 ** 2:
                            continue
                        self.add_block((x, y, z), t, immediate=False)
                s -= d
            progress = update_progress(progress, 5000)
        print()

    def hit_test(self, position, vector, max_distance=8):
        m = 8
        x, y, z = position
        dx, dy, dz = vector
        previous = None
        for _ in xrange(max_distance * m):
            key = normalize((x, y, z))
            if key != previous and key in self.world:
                return key, previous
            previous = key
            x, y, z = x + dx / m, y + dy / m, z + dz / m
        return None, None

    def exposed(self, position):
        x, y, z = position
        for dx, dy, dz in FACES:
            if (x + dx, y + dy, z + dz) not in self.world:
                return True
        return False

    def add_block(self, position, texture, immediate=True):
        if position in self.world:
            self.remove_block(position, immediate)
        self.world[position] = texture
        self.sectors.setdefault(sectorize(position), []).append(position)
        if immediate:
            if self.exposed(position):
                self.show_block(position)
            self.check_neighbors(position)

    def remove_block(self, position, immediate=True):
        # if immediate:
        #     self.world[position].destroy(self.world, *position)
        del self.world[position]
        self.sectors[sectorize(position)].remove(position)
        if immediate:
            if position in self.shown:
                self.hide_block(position)
            self.check_neighbors(position)

    def check_neighbors(self, position):
        x, y, z = position
        for dx, dy, dz in FACES:
            key = (x + dx, y + dy, z + dz)
            if key not in self.world:
                continue
            if self.exposed(key):
                if key not in self.shown:
                    self.show_block(key)
            else:
                if key in self.shown:
                    self.hide_block(key)

    def show_block(self, position, immediate=True):
        texture = self.world[position].texture
        self.shown[position] = texture
        if immediate:
            self._show_block(position, texture)
        else:
            self._enqueue(self._show_block, position, texture)

    def _show_block(self, position, texture):
        x, y, z = position
        vertex_data = cube_vertices(x, y - self.world[position].height, z, 0.5)
        texture_data = list(texture)
        self._shown[position] = self.batch.add(24, GL_QUADS, self.group,('v3f/static', vertex_data),('t2f/static', texture_data))

    def hide_block(self, position, immediate=True):
        self.shown.pop(position)
        if immediate:
            self._hide_block(position)
        else:
            self._enqueue(self._hide_block, position)

    def _hide_block(self, position):
        self._shown.pop(position).delete()

    def show_sector(self, sector):
        for position in self.sectors.get(sector, []):
            if position not in self.shown and self.exposed(position):
                self.show_block(position, False)

    def hide_sector(self, sector):
        for position in self.sectors.get(sector, []):
            if position in self.shown:
                self.hide_block(position, False)

    def change_sectors(self, before, after):
        before_set = set()
        after_set = set()
        pad = 4
        for dx in xrange(-pad, pad + 1):
            for dy in [0]:
                for dz in xrange(-pad, pad + 1):
                    if dx ** 2 + dy ** 2 + dz ** 2 > (pad + 1) ** 2:
                        continue
                    if before:
                        x, y, z = before
                        before_set.add((x + dx, y + dy, z + dz))
                    if after:
                        x, y, z = after
                        after_set.add((x + dx, y + dy, z + dz))
        show = after_set - before_set
        hide = before_set - after_set
        for sector in show:
            self.show_sector(sector)
        for sector in hide:
            self.hide_sector(sector)

    def _enqueue(self, func, *args):
        self.queue.append((func, args))

    def _dequeue(self):
        func, args = self.queue.popleft()
        func(*args)

    def process_queue(self):
        start = timefunc()
        while self.queue and timefunc() - start < 1.0 / TICKS_PER_SEC:
            self._dequeue()

    def process_entire_queue(self):
        while self.queue:
            self._dequeue()

class Window(pyglet.window.Window):
    def __init__(self, *args, **kwargs):
        super(Window, self).__init__(*args, **kwargs)

        self.saver_loader = 'pickle'
        # self.loading_image = image.load('textures/loading.png')
        # self.loaded = False
        # pyglet.clock.schedule(self._loading_screen, 1)
        # if settings.LOG_WORLD_GEN_PROGRESS:
        #     thread.start_new_thread(self._load, ())
        # else:
        #     self._init()
        self._init()
        # pyglet.app.run()

    def _load(self):
        pyglet.clock.schedule_once(self._init, 0)

    def _init(self, dt=0):
        self.exclusive = False
        self.chatbox_open = False
        self.showLabel = True
        self.flying = False
        self.running = False
        self.gamemode = 1
        self.strafe = [0, 0]
        self.position = (0, 0, 0)
        self.rotation = (0, 0)
        self.sector = None
        self.reticle = None
        self.dy = 0
        self.health = 20
        self.inventory = BLOCKS + HALFBLOCKS
        self.block = self.inventory[0]
        self.num_keys = [
            key._1, key._2, key._3, key._4, key._5,
            key._6, key._7, key._8, key._9]
        self.model = Model()
        self.clear_color = (0.5, 0.69, 1.0)
        self.label = pyglet.text.Label('', font_name='Arial', font_size=18,
            x=10, y=self.height - 10, anchor_x='left', anchor_y='top',
            color=(0, 0, 0, 255))
        self.hudLabel = pyglet.text.Label('', font_name='Arial', font_size=18,
            x=10, y=10, anchor_x='left', anchor_y='bottom',
            color=(0, 0, 0, 255))
        self.chatbox_text = pyglet.text.Label('', font_name='Arial', font_size=15,
            x=10, y=20, anchor_x='left', anchor_y='bottom',
            color=(240, 240, 240, 255))
        self.chatbox_history = []
        self.loaded = True
        pyglet.clock.schedule_interval(self.update, 1.0 / TICKS_PER_SEC)

    def _loading_screen(self, *p, **k):
        self.clear()
        self.loading_image.blit(0, 0)
        if not self.loaded:
            pyglet.clock.schedule(self._loading_screen, 1)
        else:
            del self.loaded, self.loading_image

    def set_exclusive_mouse(self, exclusive):
        super(Window, self).set_exclusive_mouse(exclusive)
        self.exclusive = exclusive

    def toggle_exclusive_mouse(self):
        self.set_exclusive_mouse(not self.exclusive)

    def get_sight_vector(self):
        x, y = self.rotation
        m = math.cos(math.radians(y))
        dy = math.sin(math.radians(y))
        dx = math.cos(math.radians(x - 90)) * m
        dz = math.sin(math.radians(x - 90)) * m
        return (dx, dy, dz)

    def get_motion_vector(self):
        if any(self.strafe):
            x, y = self.rotation
            strafe = math.degrees(math.atan2(*self.strafe))
            y_angle = math.radians(y)
            x_angle = math.radians(x + strafe)
            if self.flying:
                m = math.cos(y_angle)
                dy = math.sin(y_angle)
                if self.strafe[1]:
                    dy = 0.0
                    m = 1
                if self.strafe[0] > 0:
                    dy *= -1
                dx = math.cos(x_angle) * m
                dz = math.sin(x_angle) * m
            else:
                dy = 0.0
                dx = math.cos(x_angle)
                dz = math.sin(x_angle)
        else:
            dy = 0.0
            dx = 0.0
            dz = 0.0
        return (dx, dy, dz)

    def update(self, dt):
        self.model.process_queue()
        sector = sectorize(self.position)
        if sector != self.sector:
            self.model.change_sectors(self.sector, sector)
            if self.sector is None:
                self.model.process_entire_queue()
            self.sector = sector
        m = 8
        dt = min(dt, 0.2)
        for _ in xrange(m):
            self._update(dt / m)
        y = self.position[1]
        u = (0.5, 0.69, 1.0)
        l = (0, 0, 0)
        if y >= -20 and y < -2:
            self.clear_color = lerp(l, u, abs(1 / y))
        elif y >= -2:
            self.clear_color = u
        elif y < -20:
            self.clear_color = l
        else:
            self.clear_color = (0.5, 0.5, 0.5)
        self.clear_color += (1,)
        glClearColor(*self.clear_color)
        if y < -20:
            self.health += (y + 20) / dt
        if self.health <= 0:
            self.death()

    def _update(self, dt):
        if self.flying and self.running:
            speed = FLY_RUNNING_SPEED
        elif self.flying and not self.running:
            speed = FLYING_SPEED
        elif self.running and not self.flying:
            speed = RUNNING_SPEED
        else:
            speed = WALKING_SPEED
        d = dt * speed
        dx, dy, dz = self.get_motion_vector()
        dx, dy, dz = dx * d, dy * d, dz * d
        if not self.flying:
            self.dy -= dt * GRAVITY
            self.dy = max(self.dy, -TERMINAL_VELOCITY)
            dy += self.dy * dt
        x, y, z = self.position
        if not (self.gamemode == 4 or self.gamemode == 3):
            x, y, z = self.collide((x + dx, y + dy, z + dz), PLAYER_HEIGHT)
        else:
            x, y, z = x + dx, y + dy, z + dz
        self.position = (x, y, z)

    def death(self):
        self.health = 20
        self.position = (0, 0, 0)

    def toggle_chatbox(self):
        self.chatbox_open = not self.chatbox_open
        pass

    def collide(self, position, height):
        pad = 0.25
        p = list(position)
        np = normalize(position)
        for face in FACES:
            for i in xrange(3):
                if not face[i]:
                    continue
                d = (p[i] - np[i]) * face[i]
                if d < pad:
                    continue
                for dy in xrange(height):
                    op = list(np)
                    op[1] -= dy
                    op[i] += face[i]
                    if tuple(op) not in self.model.world:
                        continue
                    p[i] -= (d - pad) * face[i]
                    if face == (0, -1, 0) or face == (0, 1, 0):
                        self.dy = 0
                    break
        return tuple(p)

    def on_mouse_press(self, x, y, button, modifiers):
        if self.exclusive:
            if self.gamemode != 3:
                vector = self.get_sight_vector()
                block, previous = self.model.hit_test(self.position, vector)
                if (button == mouse.RIGHT) or \
                        ((button == mouse.LEFT) and (modifiers & key.MOD_CTRL)):
                    if previous and not self.position[1] == y and not self.position[1] + 1 == y:
                        self.model.add_block(previous, self.block)
                elif button == pyglet.window.mouse.LEFT and block:
                    self.model.remove_block(block)
        else:
            self.set_exclusive_mouse(True)

    def on_mouse_motion(self, x, y, dx, dy):
        if self.exclusive:
            m = 0.15
            x, y = self.rotation
            x, y = x + dx * m, y + dy * m
            y = max(-90, min(90, y))
            self.rotation = (x, y)

    def on_key_press(self, symbol, modifiers):
        if symbol == key.ESCAPE:
            self.toggle_exclusive_mouse()
            self.chatbox_open = False
        if not self.chatbox_open:
            self.on_key_press_game(symbol, modifiers)
        else:
            if symbol == key.RETURN:
                self.chatbox_send()

    def on_key_press_game(self, symbol, modifiers):
        if symbol == key.W or symbol == key.UP:
            self.strafe[0] -= 1
        elif symbol == key.S or symbol == key.DOWN:
            self.strafe[0] += 1
        elif symbol == key.A or symbol == key.LEFT:
            self.strafe[1] -= 1
        elif symbol == key.D or symbol == key.RIGHT:
            self.strafe[1] += 1
        elif symbol == key.SPACE:
            if self.dy == 0 or self.flying:
                self.dy += JUMP_SPEED
        # elif symbol == key.T or symbol == key.SLASH:
        #     self.set_exclusive_mouse(False)
        #     self.chatbox_open = True
        elif symbol == key.C:
            self.command_exec(input('/'))
        elif symbol == key.TAB:
            if not (self.gamemode == 3 or self.gamemode == 4):
                self.flying = not self.flying
        elif modifiers & key.MOD_ALT:
            self.running = not self.running
        elif symbol in self.num_keys and modifiers & key.MOD_CTRL:
            index = (symbol - self.num_keys[0]) % len(self.inventory)
            self.block = self.inventory[index + 20]
        elif symbol == key._0 and modifiers & key.MOD_CTRL:
            self.block = self.inventory[29]
        elif symbol in self.num_keys and modifiers & key.MOD_SHIFT:
            index = (symbol - self.num_keys[0]) % len(self.inventory)
            self.block = self.inventory[index + 10]
        elif symbol == key._0 and modifiers & key.MOD_SHIFT:
            self.block = self.inventory[19]
        elif symbol in self.num_keys:
            index = (symbol - self.num_keys[0]) % len(self.inventory)
            self.block = self.inventory[index]
        elif symbol == key._0:
            self.block = self.inventory[9]
        elif symbol == key.F2:
            pyglet.image.get_buffer_manager().get_color_buffer().save('screenshots/screenshot' + datetime.datetime.now().isoformat() + '.png')
        elif symbol == key.F1:
            self.showLabel = not self.showLabel

    def on_key_release(self, symbol, modifiers):
        if symbol == key.W or symbol == key.UP:
            self.strafe[0] += 1
        elif symbol == key.S or symbol == key.DOWN:
            self.strafe[0] -= 1
        elif symbol == key.A or symbol == key.LEFT:
            self.strafe[1] += 1
        elif symbol == key.D or symbol == key.RIGHT:
            self.strafe[1] -= 1

    def on_resize(self, width, height):
        self.label.y = height - 10
        if self.reticle:
            self.reticle.delete()
        x, y = self.width // 2, self.height // 2
        n = 10
        self.reticle = pyglet.graphics.vertex_list(4,
            ('v2i', (x - n, y, x + n, y, x, y - n, x, y + n))
        )

    def set_2d(self):
        width, height = self.get_size()
        glDisable(GL_DEPTH_TEST)
        glViewport(0, 0, width, height)
        glMatrixMode(GL_PROJECTION)
        glLoadIdentity()
        glOrtho(0, width, 0, height, -1, 1)
        glMatrixMode(GL_MODELVIEW)
        glLoadIdentity()

    def set_3d(self):
        width, height = self.get_size()
        glEnable(GL_DEPTH_TEST)
        glViewport(0, 0, width, height)
        glMatrixMode(GL_PROJECTION)
        glLoadIdentity()
        gluPerspective(65.0, width / float(height), 0.1, 60.0)
        glMatrixMode(GL_MODELVIEW)
        glLoadIdentity()
        x, y = self.rotation
        glRotatef(x, 0, 1, 0)
        glRotatef(-y, math.cos(math.radians(x)), 0, math.sin(math.radians(x)))
        x, y, z = self.position
        glTranslatef(-x, -y, -z)

    def on_draw(self):
        self.clear()
        self.set_3d()
        glColor3d(1, 1, 1)
        self.model.batch.draw()
        self.draw_focused_block()
        self.set_2d()
        if not self.chatbox_open:
            if self.showLabel: self.draw_label()
            if self.showLabel: self.draw_reticle()
        else:
            self.draw_chatbox()

    def draw_focused_block(self):
        vector = self.get_sight_vector()
        block = self.model.hit_test(self.position, vector)[0]
        if block and self.gamemode != 3:
            x, y, z = block
            vertex_data = cube_vertices(x, y - self.model.world[block].height, z, 0.51)
            glColor3d(0, 0, 0)
            glPolygonMode(GL_FRONT_AND_BACK, GL_LINE)
            pyglet.graphics.draw(24, GL_QUADS, ('v3f/static', vertex_data))
            glPolygonMode(GL_FRONT_AND_BACK, GL_FILL)

    def draw_chatbox(self):
        self.chatbox_text.draw()

    def on_text(self, text):
        if self.chatbox_open:
            print(self.chatbox.text, text)
            self.chatbox_text.text = self.chatbox_text.text + text

    def chatbox_send(self):
        text = str(self.chatbox_text.text)
        print(text)
        print(text[0])
        # self.chatbox_text.text = ''
        print('tmp_reset')
        self.chatbox_text = pyglet.text.Label('', font_name='Arial', font_size=15,
            x=10, y=20, anchor_x='left', anchor_y='bottom',
            color=(240, 240, 240, 255))
        if text[0] == '/':
            self.command_exec(text)
        else:
            self.chatbox_history.append(text)

    def set_gamemode(self, mode):
        self.gamemode = mode
        if mode == 3 or mode == 4:
            self.flying = True

    def command_exec(self, cmd):
        cmd = cmd.lstrip('/')
        # print(cmd)
        if ' ' in cmd:
            cmd, args = cmd.split(' ', 1)
        else: args = ''
        if cmd == 'tp' or cmd == 'teleport':
            pos = tuple(int(x) for x in args.split(' '))
            self.position = pos
            print('Teleported Player to %i, %i, %i' % pos)
        elif cmd == 'kill':
            self.death()
            print('Killed Player')
        elif cmd == 'gamemode':
            self.set_gamemode(int(self.args))
        elif cmd == 'loadseed':
            random.seed(int(args))
            self.world = Model()
        elif cmd == 'newworld':
            self.world = Model()
            self.position = (0, 0, 0)
            self.rotation = (0, 0)
        elif cmd == 'seed':
            print(random.seed())
        elif cmd == 'savefmt':
            self.saver_loader = args
        elif cmd == 'save':
            # saver = __import__(self.saver_loader + '_format')
            saver = settings.saver_loader
            print(dir(saver))
            print(type(saver.save))
            saver.save(self.args, world=self.world, position=self.position, rotation=self.rotation)
        elif cmd == 'load':
            # loader = __import__(self.saver_loader + '_format')
            loader = settings.saver_loader
            val = loader.load(self.args)
            self.world = val['world']
            self.position = val['position']
            self.rotation = val['rotation']
        elif cmd == 'say':
            print(args)

    def draw_label(self):
        x, y, z = self.position
        self.label.text = '%02d (%.2f, %.2f, %.2f) %d / %d' % (
            pyglet.clock.get_fps(), x, y, z,
            len(self.model._shown), len(self.model.world))
        self.hudLabel.text = 'CurrentBlock:%s Health:%i' % (
            self.block.name, self.health
        )
        self.label.draw()
        if self.gamemode != 3:
            self.hudLabel.draw()

    def draw_reticle(self):
        glColor3d(0, 0, 0)
        if self.gamemode != 3:
            self.reticle.draw(GL_LINES)

def setup():
    glClearColor(0.5, 0.69, 1.0, 1)
    glEnable(GL_CULL_FACE)
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_NEAREST)
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_NEAREST)
    glEnable(GL_BLEND)
    glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)

def main():
    window = Window(width=800, height=600, caption='PygCraft', resizable=True)
    window.set_exclusive_mouse(True)
    setup()
    pyglet.app.run()

if __name__ == '__main__':
    main()
