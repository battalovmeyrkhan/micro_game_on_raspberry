# =============================================================================
# games.py — MicroPython Game System for Raspberry Pi Pico
# pibody library | Display 240x320
# =============================================================================

from pibody import LED, Buzzer, Button, Joystick, Switch
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
switch   = Switch("D")
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

def sound_enabled():
    return switch.value() == 1

def beep(freq, volume, duration):
    # если выключен switch — вообще не издаем звук
    if not sound_enabled():
        return

    try:
        buzzer.make_sound(freq, volume, duration)
    except TypeError:
        try:
            buzzer.make_sound(freq, volume, duration, False)
        except:
            pass
    except:
        pass

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

            if updated and self._alive:
                self._draw_partial()

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
                        wait_btn_release()
                        break

                    sleep(0.05)

            sleep(0.03)

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

        self._last_old_head = None
        self._last_new_head = None
        self._last_old_tail = None

        self._draw_static()
        self._draw_full_snake()

    def _cell_xy(self, c, r):
        return c * self.CELL + 1, r * self.CELL + 1

    def _draw_cell(self, c, r, color):
        x, y = self._cell_xy(c, r)
        display.fill_rect(x, y, self.CELL - 2, self.CELL - 2, color)

    def _draw_static(self):
        display.fill(BLACK)
        display.rect(0, 0, DW, DH, GREEN)

        fc, fr = self._food
        self._draw_cell(fc, fr, RED)

        display.fill_rect(0, 0, 120, 16, BLACK)
        display.text("Score:" + str(self._score), 4, 4)

    def _draw_full_snake(self):
        for i, (c, r) in enumerate(self._snake):
            self._draw_cell(c, r, WHITE if i == 0 else GREEN)

    def _draw_score(self):
        display.fill_rect(0, 0, 120, 16, BLACK)
        display.text("Score:" + str(self._score), 4, 4)

    def _place_food(self):
        while True:
            f = (
                randint(1, self.COLS - 2),
                randint(1, self.ROWS - 2)
            )
            if f not in self._snake:
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

        old_head = self._snake[0]
        old_tail = None

        self._snake.insert(0, new_head)

        if new_head == self._food:
            self._score += 1
            led.toggle()
            beep(900, 0.6, 0.05)

            self._place_food()
            fc, fr = self._food
            self._draw_cell(fc, fr, RED)
            self._draw_score()

            if self._speed > 2:
                self._speed -= 1
        else:
            old_tail = self._snake.pop()

        self._last_old_head = old_head
        self._last_new_head = new_head
        self._last_old_tail = old_tail

    def _draw_partial(self):
        old_head = self._last_old_head
        new_head = self._last_new_head
        old_tail = self._last_old_tail

        if old_head is not None:
            self._draw_cell(old_head[0], old_head[1], GREEN)

        if new_head is not None:
            self._draw_cell(new_head[0], new_head[1], WHITE)

        if old_tail is not None:
            self._draw_cell(old_tail[0], old_tail[1], BLACK)

    def _show_game_over(self):
        beep(300, 0.8, 0.4)
        led.off()
        display.fill(BLACK)
        display.text("GAME OVER", 70, 120)
        display.text("Release = Restart", 45, 150)
        display.text("Hold A = Menu", 55, 180)
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

    plx, ply, plw, plh = PLATFORMS[3]

    FLAG_X = plx + plw - 70
    FLAG_Y = ply - 30

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

            if self._exit_to_menu:
                led.off()
                return

            if self._won:
                self._win_screen()
                led.off()
                return

            self._draw_partial()
            sleep(0.05)

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

        self._prev_px = int(self._px)
        self._prev_py = int(self._py)
        self._prev_ex = int(self._ex)
        self._prev_ey = int(self._ey)
        self._prev_enemy_alive = self._enemy_alive
        self._score_dirty = True

        self._draw_static()
        self._draw_player(int(self._px), int(self._py))
        if self._enemy_alive:
            self._draw_enemy(int(self._ex), int(self._ey))

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
        # сохранить старые позиции перед движением
        self._prev_px = int(self._px)
        self._prev_py = int(self._py)
        self._prev_ex = int(self._ex)
        self._prev_ey = int(self._ey)
        self._prev_enemy_alive = self._enemy_alive

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
                    self._score_dirty = True
                    beep(600, 0.6, 0.07)
                    led.toggle()
                else:
                    self._death_screen()
                    return

        player_x = int(self._px)
        player_y = int(self._py)

        if (
            player_x + self.PW >= self.FLAG_X and
            player_x <= self.FLAG_X + 10 and
            player_y + self.PH >= self.FLAG_Y and
            player_y <= self.FLAG_Y + 30
        ):
            self._won = True

    # -------------------------------------------------------------------------
    # DRAW HELPERS
    # -------------------------------------------------------------------------
    def _draw_static(self):
        display.fill(BLACK)

        for i, (plx, ply, plw, plh) in enumerate(self.PLATFORMS):
            display.fill_rect(plx, ply, plw, plh, GREEN if i == 0 else YELLOW)

        display.line(self.FLAG_X, self.FLAG_Y, self.FLAG_X, self.FLAG_Y + 30, WHITE)
        display.fill_rect(self.FLAG_X + 1, self.FLAG_Y, 10, 8, RED)

        self._draw_score()

    def _draw_score(self):
        display.fill_rect(0, 0, DW, 16, BLACK)
        display.text("Pts:" + str(self._score), 4, 4)
        display.text("HoldA=back", 140, 4)
        self._score_dirty = False

    def _draw_player(self, px, py):
        display.fill_rect(px, py + 4, self.PW, self.PH - 4, CYAN)
        display.fill_rect(px, py, self.PW, 6, RED)

    def _draw_enemy(self, ex, ey):
        display.fill_rect(ex, ey, self.EW, self.EH, RED)
        display.pixel(ex + 2, ey + 2, WHITE)
        display.pixel(ex + 10, ey + 2, WHITE)

    def _restore_bg_rect(self, x, y, w, h):
        # базовый фон
        display.fill_rect(x, y, w, h, BLACK)

        # восстановить платформы в области
        for i, (plx, ply, plw, plh) in enumerate(self.PLATFORMS):
            if self._rects_overlap(x, y, w, h, plx, ply, plw, plh):
                color = GREEN if i == 0 else YELLOW
                ix1 = max(x, plx)
                iy1 = max(y, ply)
                ix2 = min(x + w, plx + plw)
                iy2 = min(y + h, ply + plh)
                if ix2 > ix1 and iy2 > iy1:
                    display.fill_rect(ix1, iy1, ix2 - ix1, iy2 - iy1, color)

        # восстановить флагшток, если зона его задела
        if self._rects_overlap(x, y, w, h, self.FLAG_X, self.FLAG_Y, 1, 31):
            line_y1 = max(y, self.FLAG_Y)
            line_y2 = min(y + h, self.FLAG_Y + 31)
            if line_y2 > line_y1:
                display.line(self.FLAG_X, line_y1, self.FLAG_X, line_y2 - 1, WHITE)

        # восстановить флаг, если зона его задела
        if self._rects_overlap(x, y, w, h, self.FLAG_X + 1, self.FLAG_Y, 10, 8):
            ix1 = max(x, self.FLAG_X + 1)
            iy1 = max(y, self.FLAG_Y)
            ix2 = min(x + w, self.FLAG_X + 11)
            iy2 = min(y + h, self.FLAG_Y + 8)
            if ix2 > ix1 and iy2 > iy1:
                display.fill_rect(ix1, iy1, ix2 - ix1, iy2 - iy1, RED)

    def _draw_partial(self):
        # стереть старого игрока
        self._restore_bg_rect(self._prev_px, self._prev_py, self.PW, self.PH)

        # стереть старого врага
        if self._prev_enemy_alive:
            self._restore_bg_rect(self._prev_ex, self._prev_ey, self.EW, self.EH)

        # если счёт изменился, обновить HUD
        if self._score_dirty:
            self._draw_score()

        # нарисовать нового игрока
        self._draw_player(int(self._px), int(self._py))

        # нарисовать нового врага
        if self._enemy_alive:
            self._draw_enemy(int(self._ex), int(self._ey))

    # -------------------------------------------------------------------------
    # SCREENS
    # -------------------------------------------------------------------------
    def _death_screen(self):
        beep(250, 0.9, 0.5)
        led.off()
        display.fill(BLACK)
        display.text("YOU DIED", 85, 140)
        display.text("Release A", 82, 175)
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
        sleep(0.4)
        wait_btn_release()

    # -------------------------------------------------------------------------
    # GEOMETRY
    # -------------------------------------------------------------------------
    @staticmethod
    def _hspan(ax, aw, bx, bw):
        return ax < bx + bw and ax + aw > bx

    @staticmethod
    def _aabb(ax, ay, aw, ah, bx, by, bw, bh):
        return ax < bx + bw and ax + aw > bx and ay < by + bh and ay + ah > by

    @staticmethod
    def _rects_overlap(ax, ay, aw, ah, bx, by, bw, bh):
        return ax < bx + bw and ax + aw > bx and ay < by + bh and ay + ah > by
    
# =============================================================================
# PONG GAME

class PongGame:
    PADDLE_W = 6
    PADDLE_H = 40
    BALL_SIZE = 6

    PLAYER_X = 10
    AI_X = DW - 16

    WIN_SCORE = 5
    PADDLE_SPEED = 6
    AI_SPEED = 4

    BALL_START_VX = 4
    BALL_START_VY = 2

    def run(self):
        self._reset()
        led.on()
        wait_btn_release()

        while True:
            pressed, released, long_hold = _btn_tracker.update()

            if long_hold:
                led.off()
                return

            self._handle_input()
            self._update()

            if self._game_over:
                self._show_result()
                led.off()
                return

            self._draw_partial()
            sleep(0.03)

    def _reset(self):
        self._player_y = DH // 2 - self.PADDLE_H // 2
        self._ai_y = DH // 2 - self.PADDLE_H // 2

        self._player_score = 0
        self._ai_score = 0
        self._game_over = False

        self._prev_player_y = self._player_y
        self._prev_ai_y = self._ai_y
        self._prev_ball_x = DW // 2
        self._prev_ball_y = DH // 2
        self._score_dirty = True

        self._serve(direction=1)
        self._draw_static()
        self._draw_score()
        self._draw_objects_full()

    def _serve(self, direction=1):
        self._ball_x = DW // 2
        self._ball_y = DH // 2
        self._ball_vx = self.BALL_START_VX * direction
        self._ball_vy = self.BALL_START_VY

        self._prev_ball_x = self._ball_x
        self._prev_ball_y = self._ball_y

    def _handle_input(self):
        d = joy_direction()

        self._prev_player_y = self._player_y

        if d == UP:
            self._player_y -= self.PADDLE_SPEED
        elif d == DOWN:
            self._player_y += self.PADDLE_SPEED

        if self._player_y < 0:
            self._player_y = 0
        if self._player_y > DH - self.PADDLE_H:
            self._player_y = DH - self.PADDLE_H

    def _update(self):
        self._prev_ai_y = self._ai_y
        self._prev_ball_x = self._ball_x
        self._prev_ball_y = self._ball_y

        # AI
        ai_center = self._ai_y + self.PADDLE_H // 2
        ball_center = self._ball_y + self.BALL_SIZE // 2

        if ai_center < ball_center:
            self._ai_y += self.AI_SPEED
        elif ai_center > ball_center:
            self._ai_y -= self.AI_SPEED

        if self._ai_y < 0:
            self._ai_y = 0
        if self._ai_y > DH - self.PADDLE_H:
            self._ai_y = DH - self.PADDLE_H

        # Ball
        self._ball_x += self._ball_vx
        self._ball_y += self._ball_vy

        # Top/bottom bounce
        if self._ball_y <= 0:
            self._ball_y = 0
            self._ball_vy = -self._ball_vy
            beep(700, 0.3, 0.03)

        if self._ball_y + self.BALL_SIZE >= DH:
            self._ball_y = DH - self.BALL_SIZE
            self._ball_vy = -self._ball_vy
            beep(700, 0.3, 0.03)

        # Player collision
        if (
            self._ball_x <= self.PLAYER_X + self.PADDLE_W and
            self._ball_x + self.BALL_SIZE >= self.PLAYER_X and
            self._ball_y + self.BALL_SIZE >= self._player_y and
            self._ball_y <= self._player_y + self.PADDLE_H
        ):
            self._ball_x = self.PLAYER_X + self.PADDLE_W
            self._ball_vx = abs(self._ball_vx)

            offset = (self._ball_y + self.BALL_SIZE // 2) - (self._player_y + self.PADDLE_H // 2)
            self._ball_vy = max(-6, min(6, offset // 3))
            beep(900, 0.4, 0.03)

        # AI collision
        if (
            self._ball_x + self.BALL_SIZE >= self.AI_X and
            self._ball_x <= self.AI_X + self.PADDLE_W and
            self._ball_y + self.BALL_SIZE >= self._ai_y and
            self._ball_y <= self._ai_y + self.PADDLE_H
        ):
            self._ball_x = self.AI_X - self.BALL_SIZE
            self._ball_vx = -abs(self._ball_vx)

            offset = (self._ball_y + self.BALL_SIZE // 2) - (self._ai_y + self.PADDLE_H // 2)
            self._ball_vy = max(-6, min(6, offset // 3))
            beep(900, 0.4, 0.03)

        # Score
        if self._ball_x < 0:
            self._ai_score += 1
            self._score_dirty = True
            beep(300, 0.5, 0.08)

            if self._ai_score >= self.WIN_SCORE:
                self._game_over = True
            else:
                self._clear_ball(self._prev_ball_x, self._prev_ball_y)
                self._draw_score()
                self._serve(direction=1)
                self._draw_ball(self._ball_x, self._ball_y)

        elif self._ball_x > DW:
            self._player_score += 1
            self._score_dirty = True
            led.toggle()
            beep(1200, 0.5, 0.08)

            if self._player_score >= self.WIN_SCORE:
                self._game_over = True
            else:
                self._clear_ball(self._prev_ball_x, self._prev_ball_y)
                self._draw_score()
                self._serve(direction=-1)
                self._draw_ball(self._ball_x, self._ball_y)

    # ------------------------------------------------------------------
    # Draw helpers
    # ------------------------------------------------------------------
    def _draw_static(self):
        display.fill(BLACK)

        y = 0
        while y < DH:
            display.fill_rect(DW // 2 - 1, y, 2, 10, WHITE)
            y += 18

        display.text("HoldA=back", 120, DH - 15)

    def _draw_score(self):
        display.fill_rect(DW // 2 - 40, 0, 80, 20, BLACK)
        display.text(str(self._player_score), DW // 2 - 30, 10)
        display.text(str(self._ai_score), DW // 2 + 20, 10)
        self._score_dirty = False

    def _draw_paddle(self, x, y, color):
        display.fill_rect(x, y, self.PADDLE_W, self.PADDLE_H, color)

    def _draw_ball(self, x, y):
        display.fill_rect(x, y, self.BALL_SIZE, self.BALL_SIZE, WHITE)

    def _clear_ball(self, x, y):
        display.fill_rect(x, y, self.BALL_SIZE, self.BALL_SIZE, BLACK)
        self._restore_center_line_rect(x, y, self.BALL_SIZE, self.BALL_SIZE)

    def _clear_paddle(self, x, y):
        display.fill_rect(x, y, self.PADDLE_W, self.PADDLE_H, BLACK)
        self._restore_center_line_rect(x, y, self.PADDLE_W, self.PADDLE_H)

    def _restore_center_line_rect(self, x, y, w, h):
        line_x = DW // 2 - 1
        if x < line_x + 2 and x + w > line_x:
            seg_y = 0
            while seg_y < DH:
                seg_h = 10
                if y < seg_y + seg_h and y + h > seg_y:
                    iy1 = max(y, seg_y)
                    iy2 = min(y + h, seg_y + seg_h)
                    if iy2 > iy1:
                        display.fill_rect(line_x, iy1, 2, iy2 - iy1, WHITE)
                seg_y += 18

    def _draw_objects_full(self):
        self._draw_paddle(self.PLAYER_X, self._player_y, GREEN)
        self._draw_paddle(self.AI_X, self._ai_y, RED)
        self._draw_ball(self._ball_x, self._ball_y)

    def _draw_partial(self):
        # erase old
        self._clear_paddle(self.PLAYER_X, self._prev_player_y)
        self._clear_paddle(self.AI_X, self._prev_ai_y)
        self._clear_ball(self._prev_ball_x, self._prev_ball_y)

        # redraw score only if changed
        if self._score_dirty:
            self._draw_score()

        # draw new
        self._draw_paddle(self.PLAYER_X, self._player_y, GREEN)
        self._draw_paddle(self.AI_X, self._ai_y, RED)
        self._draw_ball(self._ball_x, self._ball_y)

    def _show_result(self):
        display.fill(BLACK)

        if self._player_score > self._ai_score:
            display.text("YOU WIN!", 85, 130)
        else:
            display.text("YOU LOSE!", 80, 130)

        display.text("Score: {}-{}".format(self._player_score, self._ai_score), 72, 160)
        display.text("Release A", 82, 195)
        sleep(0.4)
        wait_btn_release()
# =============================================================================
# LAUNCHER MENU
# =============================================================================
_GAMES = [
    ("Snake", SnakeGame),
    ("Mario", MarioGame),
    ("Pong", PongGame),
]
def draw_menu_base():
    display.fill(BLACK)
    display.text("=  GAME  MENU  =", 28, 30)

    for i, (name, _cls) in enumerate(_GAMES):
        y = 90 + i * 40
        display.text(name, 70, y)

    display.text("A = launch game", 35, DH - 50)
    display.text("Hold A = menu", 40, DH - 30)

def draw_cursor(row, selected):
    y = 90 + row * 40
    mark = ">" if selected else " "
    display.fill_rect(50, y, 12, 12, BLACK)
    display.text(mark, 50, y)

def main_menu():
    sel = 0
    n = len(_GAMES)
    wait_btn_release()

    draw_menu_base()
    draw_cursor(sel, True)
    refresh()

    while True:
        pressed, released, long_hold = _btn_tracker.update()

        old_sel = sel
        d = _joy_edge.get()

        if d == UP:
            sel = (sel - 1) % n
        elif d == DOWN:
            sel = (sel + 1) % n

        if sel != old_sel:
            draw_cursor(old_sel, False)
            draw_cursor(sel, True)
            beep(700, 0.4, 0.04)
            refresh()

        if pressed:
            beep(1000, 0.5, 0.05)
            _GAMES[sel][1]().run()
            wait_btn_release()

            
            draw_menu_base()
            draw_cursor(sel, True)
            refresh()

        sleep(0.08)

# =============================================================================
# START
# =============================================================================
main_menu()
