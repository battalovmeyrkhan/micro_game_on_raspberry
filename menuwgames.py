# =============================================================================
# games.py — MicroPython Game System for Raspberry Pi Pico
# pibody library | Display 240x320
# =============================================================================

from pibody import LED, Buzzer, Button, Joystick
from pibody import display as _display_obj
from time import sleep, ticks_ms, ticks_diff

try:
    import urandom as _rand
    def randint(a, b):
        return _rand.randint(a, b)
except ImportError:
    import random as _rand
    def randint(a, b):
        return _rand.randint(a, b)

# -----------------------------------------------------------------------------
# Hardware
# -----------------------------------------------------------------------------
btn      = Button("A")
led      = LED("B")
joystick = Joystick("F")
buzzer   = Buzzer("C")
display  = _display_obj

# -----------------------------------------------------------------------------
# Colours
# -----------------------------------------------------------------------------
BLACK   = display.BLACK
WHITE   = display.WHITE
RED     = display.RED
GREEN   = display.GREEN
BLUE    = display.BLUE
YELLOW  = display.YELLOW
CYAN    = display.CYAN
MAGENTA = display.MAGENTA

DW = display.width
DH = display.height

# =============================================================================
# SAFE HELPERS
# =============================================================================

def refresh():
    # This display updates immediately, no display.show()
    pass

def beep(freq, volume, duration):
    try:
        buzzer.make_sound(freq, volume, duration)
    except TypeError:
        try:
            buzzer.make_sound(freq, volume, duration, False)
        except Exception:
            pass
    except Exception:
        pass

# =============================================================================
# INPUT HELPERS
# =============================================================================

UP     = 0
DOWN   = 1
LEFT   = 2
RIGHT  = 3
CENTER = 4

# Joystick returns float around 0.0..1.0, center near 0.5
_JOY_LO = 0.35
_JOY_HI = 0.65

def joy_direction():
    x = joystick.read_x()
    y = joystick.read_y()

    # Inverted Y to match physical direction
    if y < _JOY_LO:
        return DOWN
    elif y > _JOY_HI:
        return UP
    elif x < _JOY_LO:
        return LEFT
    elif x > _JOY_HI:
        return RIGHT
    return CENTER

def joy_raw():
    return joystick.read_x(), joystick.read_y()

# -----------------------------------------------------------------------------
# Simple button helpers
# -----------------------------------------------------------------------------
_btn_idle = btn.value()
_btn_active = 0 if _btn_idle == 1 else 1

def btn_is_down():
    return btn.value() == _btn_active

def wait_btn_release():
    while btn_is_down():
        sleep(0.01)

class ButtonTracker:
    def __init__(self, hold_ms=700):
        self.hold_ms = hold_ms
        self.was_down = False
        self.down_at = 0
        self.long_fired = False

    def update(self):
        now = ticks_ms()
        down = btn_is_down()

        pressed = False
        released = False
        long_hold = False

        if down and not self.was_down:
            self.was_down = True
            self.down_at = now
            self.long_fired = False
            pressed = True

        elif not down and self.was_down:
            self.was_down = False
            released = True
            self.long_fired = False

        elif down and self.was_down and not self.long_fired:
            if ticks_diff(now, self.down_at) >= self.hold_ms:
                self.long_fired = True
                long_hold = True

        return pressed, released, long_hold

_btn_tracker = ButtonTracker(700)

# -----------------------------------------------------------------------------
# Joystick edge detector
# -----------------------------------------------------------------------------
class _JoyEdge:
    def __init__(self, cooldown_ms=180):
        self._prev = CENTER
        self._cooldown = cooldown_ms
        self._last_t = 0

    def get(self):
        now = ticks_ms()
        if ticks_diff(now, self._last_t) < self._cooldown:
            return CENTER

        d = joy_direction()

        if d != CENTER:
            if d != self._prev:
                self._prev = d
                self._last_t = now
                return d
        else:
            self._prev = CENTER

        return CENTER

_joy_edge = _JoyEdge()

# =============================================================================
# SNAKE GAME
# =============================================================================
class SnakeGame:
    CELL = 20
    COLS = DW // CELL
    ROWS = DH // CELL

    def run(self):
        self._reset()
        led.on()
        wait_btn_release()
        self._draw()

        while True:
            pressed, released, long_hold = _btn_tracker.update()
            self._handle_input()

            if long_hold:
                led.off()
                return

            updated = False

            self._tick += 1
            if self._tick >= self._speed:
                self._tick = 0
                self._update()
                updated = True

            if updated:
                self._draw()

            if not self._alive:
                self._show_game_over()
                wait_btn_release()

                while True:
                    pressed, released, long_hold = _btn_tracker.update()

                    if long_hold:
                        led.off()
                        return

                    if released:
                        self._reset()
                        self._draw()
                        wait_btn_release()
                        break

                    sleep(0.05)

            sleep(0.05)

    def _reset(self):
        cx, cy = self.COLS // 2, self.ROWS // 2
        self._snake = [(cx, cy), (cx - 1, cy), (cx - 2, cy)]
        self._dir = RIGHT
        self._next = RIGHT
        self._score = 0
        self._alive = True
        self._tick = 0
        self._speed = 8
        self._place_food()

    def _place_food(self):
     while True:
        f = (
            randint(1, self.COLS - 2),
            randint(1, self.ROWS - 2)
        )
        if f not in self._snake and f != self._snake[0]:
            self._food = f
            return

    def _handle_input(self):
        d = _joy_edge.get()

        if d == UP and self._dir != DOWN:
            self._next = UP
        elif d == DOWN and self._dir != UP:
            self._next = DOWN
        elif d == LEFT and self._dir != RIGHT:
            self._next = LEFT
        elif d == RIGHT and self._dir != LEFT:
            self._next = RIGHT

    def _update(self):
        self._dir = self._next
        hc, hr = self._snake[0]

        if self._dir == UP:
            hr -= 1
        elif self._dir == DOWN:
            hr += 1
        elif self._dir == LEFT:
            hc -= 1
        elif self._dir == RIGHT:
            hc += 1

        if not (0 <= hc < self.COLS and 0 <= hr < self.ROWS):
            self._alive = False
            return

        new_head = (hc, hr)

        if new_head in self._snake:
            self._alive = False
            return

        self._snake.insert(0, new_head)

        if new_head == self._food:
            self._score += 1
            led.toggle()
            beep(900, 0.6, 0.05)
            self._place_food()
            if self._speed > 2:
                self._speed -= 1
        else:
            self._snake.pop()

    def _draw(self):
        display.fill(BLACK)
        display.rect(0, 0, DW, DH, GREEN)

        fc, fr = self._food
        display.fill_rect(fc * self.CELL + 1, fr * self.CELL + 1,
                          self.CELL - 2, self.CELL - 2, RED)

        for i, (sc, sr) in enumerate(self._snake):
            color = WHITE if i == 0 else GREEN
            display.fill_rect(sc * self.CELL + 1, sr * self.CELL + 1,
                              self.CELL - 2, self.CELL - 2, color)

        display.text("Score:" + str(self._score), 4, 4)
        refresh()

    def _show_game_over(self):
        beep(300, 0.8, 0.4)
        led.off()
        display.fill(BLACK)
        display.text("GAME OVER", 70, 120)
        display.text("Release = Restart", 45, 150)
        display.text("Hold A = Menu", 55, 180)
        refresh()
        sleep(0.3)

# =============================================================================
# MARIO GAME
# =============================================================================
class MarioGame:
    GRAVITY  = 1
    JUMP_V   = -14
    WALK_SPD = 3

    PW, PH = 14, 18
    EW, EH = 14, 12

    GY = DH - 30

    PLATFORMS = [
        (0,   GY,  DW, 30),
        (20,  240, 80,  8),
        (130, 190, 80,  8),
        (40,  140, 80,  8),
    ]

    FLAG_X = DW - 30
    FLAG_Y = PLATFORMS[3][1] - 32

    def run(self):
        self._reset()
        led.on()
        wait_btn_release()

        while True:
            pressed, released, long_hold = _btn_tracker.update()

            if long_hold:
                led.off()
                return

            self._handle_input(pressed)
            self._update()
            self._draw()

            if self._exit_to_menu:
                led.off()
                return

            if self._won:
                self._win_screen()
                led.off()
                return

            sleep(0.06)

    def _reset(self):
        self._px = 10.0
        self._py = float(self.GY - self.PH)
        self._pvx = 0.0
        self._pvy = 0.0
        self._on_ground = True

        self._ex = 100.0
        self._ey = float(self.GY - self.EH)
        self._evx = 1.5
        self._enemy_alive = True

        self._score = 0
        self._won = False
        self._exit_to_menu = False

    def _handle_input(self, pressed):
        x, _ = joy_raw()

        if x < _JOY_LO:
            self._pvx = -self.WALK_SPD
        elif x > _JOY_HI:
            self._pvx = self.WALK_SPD
        else:
            self._pvx = 0

        if pressed and self._on_ground:
            self._pvy = self.JUMP_V
            self._on_ground = False
            beep(700, 0.5, 0.06)

    def _update(self):
        self._pvy += self.GRAVITY
        self._px += self._pvx
        self._py += self._pvy

        self._px = max(0.0, min(float(DW - self.PW), self._px))

        self._on_ground = False
        for (plx, ply, plw, plh) in self.PLATFORMS:
            if self._hspan(int(self._px), self.PW, plx, plw):
                bot = int(self._py) + self.PH
                if self._pvy >= 0 and ply <= bot <= ply + plh + abs(int(self._pvy)) + 2:
                    self._py = float(ply - self.PH)
                    self._pvy = 0.0
                    self._on_ground = True

        if self._py > DH:
            self._death_screen()
            return

        if self._enemy_alive:
            self._ex += self._evx
            if self._ex <= 0 or self._ex + self.EW >= DW:
                self._evx = -self._evx

            self._ey = float(self.GY - self.EH)

            if self._aabb(int(self._px), int(self._py), self.PW, self.PH,
                          int(self._ex), int(self._ey), self.EW, self.EH):
                if self._pvy > 0 and int(self._py) + self.PH < int(self._ey) + self.EH // 2:
                    self._enemy_alive = False
                    self._pvy = self.JUMP_V // 2
                    self._score += 1
                    beep(600, 0.6, 0.07)
                    led.toggle()
                else:
                    self._death_screen()
                    return

        if int(self._px) + self.PW >= self.FLAG_X and int(self._py) <= self.FLAG_Y + 30:
            self._won = True

    def _draw(self):
        display.fill(BLACK)

        for i, (plx, ply, plw, plh) in enumerate(self.PLATFORMS):
            display.fill_rect(plx, ply, plw, plh, GREEN if i == 0 else YELLOW)

        display.line(self.FLAG_X, self.FLAG_Y, self.FLAG_X, self.FLAG_Y + 30, WHITE)
        display.fill_rect(self.FLAG_X + 1, self.FLAG_Y, 10, 8, RED)

        if self._enemy_alive:
            ex, ey = int(self._ex), int(self._ey)
            display.fill_rect(ex, ey, self.EW, self.EH, RED)
            display.pixel(ex + 2, ey + 2, WHITE)
            display.pixel(ex + 10, ey + 2, WHITE)

        px, py = int(self._px), int(self._py)
        display.fill_rect(px, py + 4, self.PW, self.PH - 4, CYAN)
        display.fill_rect(px, py, self.PW, 6, RED)

        display.text("Pts:" + str(self._score), 4, 4)
        display.text("HoldA=back", 140, 4)
        refresh()

    def _death_screen(self):
        beep(250, 0.9, 0.5)
        led.off()
        display.fill(BLACK)
        display.text("YOU DIED", 85, 140)
        display.text("Release A", 82, 175)
        refresh()
        sleep(0.4)
        wait_btn_release()
        self._exit_to_menu = True

    def _win_screen(self):
        beep(1200, 0.7, 0.12)
        sleep(0.15)
        beep(1500, 0.7, 0.25)
        display.fill(BLACK)
        display.text("YOU WIN!", 85, 130)
        display.text("Score: " + str(self._score), 75, 160)
        display.text("Release A", 82, 195)
        refresh()
        sleep(0.4)
        wait_btn_release()

    @staticmethod
    def _hspan(ax, aw, bx, bw):
        return ax < bx + bw and ax + aw > bx

    @staticmethod
    def _aabb(ax, ay, aw, ah, bx, by, bw, bh):
        return ax < bx + bw and ax + aw > bx and ay < by + bh and ay + ah > by

# =============================================================================
# LAUNCHER MENU
# =============================================================================
_GAMES = [
    ("Snake", SnakeGame),
    ("Mario", MarioGame),
]

def main_menu():
    sel = 0
    n = len(_GAMES)
    wait_btn_release()
    need_redraw = True

    while True:
        pressed, released, long_hold = _btn_tracker.update()

        if need_redraw:
            display.fill(BLACK)
            display.text("=  GAME  MENU  =", 28, 30)

            for i, (name, _cls) in enumerate(_GAMES):
                y = 90 + i * 40
                label = ">  " + name if i == sel else "   " + name
                display.text(label, 50, y)

            display.text("A = launch game", 35, DH - 50)
            display.text("Hold A = menu", 40, DH - 30)
            refresh()
            need_redraw = False

        d = _joy_edge.get()
        if d == UP:
            sel = (sel - 1) % n
            beep(700, 0.4, 0.04)
            need_redraw = True
        elif d == DOWN:
            sel = (sel + 1) % n
            beep(700, 0.4, 0.04)
            need_redraw = True

        if pressed:
            beep(1000, 0.5, 0.05)
            _GAMES[sel][1]().run()
            wait_btn_release()
            need_redraw = True

        sleep(0.08)

# =============================================================================
# START
# =============================================================================
main_menu()
