import atexit
import copy
import curses
import glob
import os
import pathlib
import pickle
import subprocess
import sys
import time
import traceback

scr = None
program = ''
curs_state = None


def _setup():
    global field
    global scr
    global curs_state
    scr = curses.initscr()
    atexit.register(_teardown)

    curs_state = curses.curs_set(0)
    curses.noecho()
    curses.cbreak()
    curses.set_escdelay(1)
    scr.keypad(True)
    scr.clear()

def _teardown():
    curses.nocbreak()
    scr.keypad(False)
    curses.echo()
    curses.curs_set(curs_state)
    curses.endwin()

def draw_frame(height, width, offset_y=0, offset_x=0, active=False):
    attr = curses.A_BOLD if active else curses.A_NORMAL
    scr.addstr(offset_y, offset_x,
               '╒' + '═' * (width-2) + '╕', attr)
    for i in range(height-2):
        scr.addstr(offset_y+i+1, offset_x,
                   '│' +  ' ' * (width-2) + '│', attr)
    scr.addstr(offset_y+height-1, offset_x,
               '╘' + '═' * (width-2) + '╛', attr)


class NikiError(Exception):
    pass


class Field:

    def __init__(self, size_y, size_x, offset_y=0, offset_x=0, name=''):
        self.size_y, self.size_x, self.offset_y, self.offset_x = \
            size_y, size_x, offset_y, offset_x

        self.discs = [[0 for _ in range(size_x)] for _ in range(size_y)]

        self.v_walls = [[False for _ in range(size_x + 1)] for _ in range(size_y)]
        self.h_walls = [[False for _ in range(size_x)] for _ in range(size_y + 1)]
        for x in range(size_x):
            self.h_walls[0][x] = True
            self.h_walls[-1][x] = True
        for y in range(size_y):
            self.v_walls[y][0] = True
            self.v_walls[y][-1] = True

        self.x0 = offset_x + 6
        self.y0 = offset_y + (size_y-1) * 2 + 1
        self.panel_x = self.screen_x(self.size_x-1) + 3 + 4
        self.panel_y = self.screen_y(self.size_y-1)
        self.nx = 0
        self.ny = 0
        self._direction = 0
        self.vorrat = 0
        self.zustand = None
        self.name = name

    def draw_outer(self):
        outer_y = self.size_y * 2 + 1
        for i in range(self.size_y):
            scr.addstr(self.offset_y + 1 + i*2, self.offset_x,
                       f'{self.size_y - i:2}')
        for i in range(self.size_x):
            scr.addstr(self.offset_y + outer_y, self.offset_x + 5 + 4*i,
                       f'{i+1:2}')

    def draw(self):
        self.draw_outer()

        for y, ff in enumerate(self.discs):
            for x, f in enumerate(ff):
                assert f >= 0
                scr.addstr(self.screen_y(y), self.screen_x(x),
                           '·' if f == 0 else 'o' if f == 1 else str(f))

        def xofs(x):
            return -1 if x == 0 else 1 if x == self.size_x else 0

        for y, ww in enumerate(self.v_walls):
            for x, w in enumerate(ww):
                scr.addstr(self.screen_y(y), self.screen_x(x)-2+xofs(x),
                           '│' if w else ' ')
        for y, ww in enumerate(self.h_walls):
            for x, w in enumerate(ww):
                scr.addstr(self.screen_y(y)+1, self.screen_x(x)-1,
                           ('─' if w else ' ')*3)
        for y in range(self.size_y+1):
            for x in range(self.size_x+1):
                l = self.h_walls[y][x-1] if x > 0 else False
                r = self.h_walls[y][x] if x < self.size_x else False
                u = self.v_walls[y-1][x] if y > 0 else False
                o = self.v_walls[y][x] if y < self.size_y else False
                if r:
                    if o:
                        if u:
                            c = '┼' if l else '├'
                        else:
                            c = '┴' if l else '└'
                    else:
                        if u:
                            c = '┬' if l else '┌'
                        else:
                            c = '─' if l else ' '
                else:
                    if o:
                        if u:
                            c = '┤' if l else '│'
                        else:
                            c = '┘' if l else ' '
                    else:
                        if u:
                            c = '┐' if l else ' '
                        else:
                            c = ' '
                scr.addstr(self.screen_y(y)+1, self.screen_x(x)+xofs(x)-2, c)
        for x in (self.screen_x(0) - 2, self.screen_x(self.size_x-1) + 2):
            for y in (self.screen_y(0) + 1, self.screen_y(self.size_y-1) - 1):
                scr.addstr(y, x, '─')


        d = self.direction
        assert 0 <= d <= 3
        scr.addstr(self.screen_y(self.ny), self.screen_x(self.nx),
                   '>' if d == 0 else '^' if d == 1 else '<' if d == 2 else 'v')

        panel_x = self.panel_x
        panel_y = self.panel_y
        scr.addstr(panel_y, panel_x, 'Feldname:')
        scr.addstr(panel_y + 2, panel_x, 'FOOO')
        scr.addstr(panel_y + 5, panel_x, 'Position')
        scr.addstr(panel_y + 7, panel_x, f'X={self.nx+1:2} Y={self.ny+1:2}')
        scr.addstr(panel_y + 10, panel_x, 'Vorrat')
        scr.addstr(panel_y + 12, panel_x, f'  {self.vorrat:02}')
        if self.zustand is not None:
            scr.addstr(panel_y + 15, panel_x, 'Zustand')
            if self.zustand:
                scr.addstr(panel_y + 17, panel_x + 2, 'an')
            else:
                scr.addstr(panel_y + 17, panel_x + 2, 'aus')
                scr.addstr(panel_y + 19, panel_x, '(Fehler)')

        scr.refresh()

    def get_discs(self, y, x):
        return self.discs[y][x]

    def set_discs(self, y, x, val):
        self.discs[y][x] = val
        self.draw()

    def set_h_wall(self, y, x, val):
        self.h_walls[y][x] = val
        self.draw()

    def set_v_wall(self, y, x, val):
        self.v_walls[y][x] = val
        self.draw()

    def screen_y(self, y):
        return self.y0 - y*2

    def screen_x(self, x):
        return self.x0 + x*4

    @property
    def pos(self):
        return self.ny, self.nx

    @pos.setter
    def pos(self, val):
        self.ny, self.nx = val
        self.draw()

    @property
    def direction(self):
        return self._direction

    @direction.setter
    def direction(self, val):
        self._direction = val
        self.draw()


class Word:
    def __init__(self, y, x, txt, highlight=False):
        self.y, self.x, self.txt, self.highlight = y, x, txt, highlight
        self.selected = False

    def draw(self):
        if self.selected:
            scr.addstr(self.y, self.x, self.txt, curses.A_REVERSE)
        elif self.highlight:
            scr.addstr(self.y, self.x, self.txt[0], curses.A_BOLD)
            scr.addstr(self.y, self.x+1, self.txt[1:])
        else:
            scr.addstr(self.y, self.x, self.txt)


class FileName:
    def __init__(self, y, x):
        self.y, self.x = y, x
        self.txt = ''

    def draw(self):
        scr.addstr(self.y, self.x, f'{self.txt:14}')

    def edit(self, txt=None):
        curses.curs_set(1)
        txt = (txt if txt is not None else self.txt)
        txt += '_' * (12-len(txt))
        pos = 0

        def update():
            scr.addstr(self.y, self.x, txt)
            scr.move(self.y, self.x + pos)

        while True:
            update()
            key = scr.getch()
            if key in range(ord('a'), ord('z')+1) or key in range(ord('0'), ord('9')+1):
                key = chr(key).upper()
                txt = txt[:pos] + key + txt[pos+1:]
                if pos+1 < 12:
                    pos += 1
            elif key == curses.KEY_RIGHT:
                if pos+1 < 12 and txt[pos] != '_':
                    pos += 1
            elif key == curses.KEY_LEFT:
                if pos > 0:
                    pos -= 1
            elif key == curses.KEY_BACKSPACE:
                if pos > 0:
                    pos -= 1
                    txt = txt[:pos] + txt[pos+1:] + '_'
            elif key == curses.KEY_DC:
                if txt[pos] != '_':
                    txt = txt[:pos] + txt[pos+1:] + '_'
            elif key == 27:
                self.draw()
                curses.curs_set(0)
                return None
            elif key == ord('\n'):
                break

        curses.curs_set(0)
        txt = txt.rstrip('_')
        self.txt = txt
        return txt


class Dialog:

    def set_selected(self, val):
        if self.selected >= 0:
            self.words[self.selected].selected = False
        self.selected = val
        if val >= 0:
            self.words[self.selected].selected = True
        self.draw()

    def draw(self):
        draw_frame(4, 80, self.y, 0, self.selected >= 0)
        for w in self.words:
            w.draw()
        self.filename.draw()

    def run(self):
        if self.selected == -1:
            self.set_selected(0)
        else:
            self.draw()

        first_letters = [ord(w.txt[0].lower()) for w in self.words]

        while True:
            key = scr.getch()
            if key in first_letters:
                self.set_selected(first_letters.index(key))
                self.draw()
                return self.words[self.selected].txt.upper()
            elif key == curses.KEY_RIGHT:
                self.set_selected((self.selected + 1) % len(self.words))
            elif key == curses.KEY_LEFT:
                self.set_selected((self.selected - 1) % len(self.words))
            elif key == curses.KEY_UP:
                return 'SWITCH'
            elif key == curses.KEY_DOWN:
                return 'SWITCH'
            elif key == ord('\n'):
                retval = self.words[self.selected].txt.upper()
                return retval


class FileDialog:

    def __init__(self, y, extension):
        self.y = y
        self.set_extension(extension)

    def _update_words(self):
        word_array = []
        for iy, row in enumerate(self.path_array[self.oy:self.oy+7]):
            wr = []
            for ix, p in enumerate(row):
                wr.append(Word(self.y+1+iy, 1+ix*21, p, False))
            word_array.append(wr)
        self.word_array = word_array

    def set_extension(self, extension):
        self.extension = extension
        paths = [w.split('.')[0] for w in sorted(glob.glob(f'*.{extension}'))
                 if not w == 'pyniki.py']
        path_array = []
        while paths:
            row, paths = paths[:4], paths[4:]
            path_array.append(row)
        self.path_array = path_array
        self.sy, self.sx, self.oy = -1, -1, 0
        self._update_words()

    def set_selected(self, sy, sx):
        if self.sy >= 0:
            self.word_array[self.sy-self.oy][self.sx].selected = False
        if sy < 0:
            self.draw()
            return
        self.sy, self.sx = sy, sx
        if sy - self.oy > 6:
            self.oy = sy - 6
            self._update_words()
        elif sy < self.oy:
            self.oy = sy
            self._update_words()
        if sy >= 0:
            self.word_array[sy-self.oy][sx].selected = True
        self.draw()

    def draw(self):
        draw_frame(9, 80, self.y, 0)
        for row in self.word_array:
            for w in row:
                w.draw()

    def run(self):
        self.set_selected(0, 0)

        while True:
            key = scr.getch()
            if key == curses.KEY_RIGHT:
                if self.sx + 1 < len(self.path_array[self.sy]):
                    self.set_selected(self.sy, self.sx+1)
                elif self.sy + 1 < len(self.path_array):
                    self.set_selected(self.sy+1, 0)
            elif key == curses.KEY_LEFT:
                if self.sx > 0:
                    self.set_selected(self.sy, self.sx-1)
                elif self.sy > 0:
                    self.set_selected(self.sy-1, 3)
            elif key == curses.KEY_UP:
                if self.sy > 0:
                    self.set_selected(self.sy-1, self.sx)
            elif key == curses.KEY_DOWN:
                if self.sy + 1 < len(self.path_array):
                    self.set_selected(self.sy+1, min(self.sx, len(self.path_array[self.sy+1])-1))
            elif key == ord('\n'):
                retval = self.path_array[self.sy][self.sx]
                self.set_selected(-1, -1)
                return retval
            elif key == 27:
                self.set_selected(-1, -1)
                return None



class RobotDialog(Dialog):

    def __init__(self, y):
        self.y = y
        self.words = [
            Word(y+2,  1, 'Edit', True),
            Word(y+2, 11, 'Compile', True),
            Word(y+2, 20, 'Run', True),
            Word(y+2, 30, 'New', True),
            Word(y+2, 36, 'Load', True),
            Word(y+2, 44, 'Save', True),
            Word(y+2, 50, 'Print', True),
            Word(y+2, 74, 'Quit', True),
        ]
        self.filename = FileName(self.y+1, 18)
        self.selected = -1


    def draw(self):
        super().draw()
        scr.addstr(self.y+1, 1, 'Roboterprogramm:')


class FieldDialog(Dialog):

    def __init__(self, y):
        self.y = y
        self.words = [
            Word(y+2,  1, 'Edit', True),
            Word(y+2, 11, 'Handsteuerung', True),
            Word(y+2, 30, 'New', True),
            Word(y+2, 36, 'Load', True),
            Word(y+2, 44, 'Save', True),
            Word(y+2, 50, 'Print', True),
            Word(y+2, 74, 'Quit', True),
        ]
        self.filename = FileName(self.y+1, 14)
        self.selected = -1


    def draw(self):
        super().draw()
        scr.addstr(self.y+1, 1, 'Roboterfeld:')



def wait():
    global speed
    field.draw()
    if speed > 0:
        scr.nodelay(True)
    while (key:=scr.getch()) > -1:
        if key == ord('\n') and speed == 0:
            break
        if key == ord('+'):
            if speed == 0:
                scr.nodelay(True)
            if speed < 9:
                speed += 1
        elif key == ord('-'):
            if speed == 1:
                scr.nodelay(False)
            if speed > 0:
                speed -= 1
        elif key == ord('0'):
            scr.nodelay(False)
            speed = 0
        elif key == 27:
            raise NikiError
        run_print_first_line()
    scr.nodelay(False)
    if speed > 0:
        time.sleep(0.1 + (9-speed)*0.2)


def is_free(direction):
    y, x = field.pos
    match field.direction:
        case 0:
            return not field.v_walls[y][x+1]
        case 1:
            return not field.h_walls[y+1][x]
        case 2:
            return not field.v_walls[y][x]
        case 3:
            return not field.h_walls[y][x]


def vorne_frei():
    return is_free(field.direction)


def links_frei():
    return is_free((field.direction + 1) % 4)


def rechts_frei():
    return is_free((field.direction - 1) % 4)


def hat_vorrat():
    return field.vorrat > 0


def platz_belegt():
    discs = field.get_discs(*field.pos)
    return discs > 0


def nimm_auf():
    if not platz_belegt():
        raise NikiError
    if field.vorrat == 99:
        raise NikiError
    y, x = field.pos
    field.set_discs(y, x, field.get_discs(y, x) - 1)
    field.vorrat += 1
    wait()


def gib_ab():
    if not hat_vorrat():
        raise NikiError
    y, x = field.pos
    discs = field.get_discs(*field.pos)
    if discs == 9:
        raise NikiError
    field.set_discs(y, x, discs + 1)
    field.vorrat -= 1
    wait()


def vor():
    if not vorne_frei():
        raise NikiError()
    y, x = field.pos
    match field.direction:
        case 0:
            field.pos = [y, x+1]
        case 1:
            field.pos = [y+1, x]
        case 2:
            field.pos = [y, x-1]
        case 3:
            field.pos = [y-1, x]
    wait()


def drehe_links():
    field.direction = (field.direction + 1) % 4
    wait()


def print_highlight_first(*words):
    first = True
    for w in words:
        if not first:
            scr.addstr('  ')
        first = False
        scr.addstr(w[0], curses.A_BOLD)
        scr.addstr(w[1:])


def print_highlight(txt):
    highlight = False
    for t in txt.split('@'):
        if highlight:
            scr.addstr(t, curses.A_BOLD)
        else:
            scr.addstr(t)
        highlight = not highlight


def print_first_line(txt):
    scr.move(0, 0)
    scr.addstr(' ' * 80)
    scr.move(0, 0)
    print_highlight(txt)


def print_last_line(txt):
    scr.move(24, 0)
    scr.addstr(' ' * 80)
    scr.move(24, 0)
    print_highlight(txt)


def edit_field():
    scr.clear()
    field.draw()
    curses.curs_set(1)
    y, x = 0, 0

    def std_fist_line():
        print_first_line(
            '@P@osition @R@ichtung @l@egen @w@egnehmen @H@indernis @a@bräumen @V@orrat @q@uit'
        )

    def update_cursor():
        scr.move(field.screen_y(y), field.screen_x(x))

    while True:
        std_fist_line()
        update_cursor()

        key = scr.getch()
        if key == ord('q'):
            break
        elif key == curses.KEY_RIGHT:
            x = (x + 1) % field.size_x
        elif key == curses.KEY_LEFT:
            x = (x - 1) % field.size_x
        elif key == curses.KEY_UP:
            y = (y + 1) % field.size_y
        elif key == curses.KEY_DOWN:
            y = (y - 1) % field.size_y
        elif key == ord('p'):
            field.pos = [y, x]
        elif key == ord('r'):
            print_first_line('@N@ord @W@est @S@üd @O@st')
            update_cursor()
            directions = [ord(d) for d in ['o', 'n', 'w', 's']]
            while True:
                key = scr.getch()
                if key in directions:
                    field.direction = directions.index(key)
                    break
        elif key in [ord('h'), ord('a')]:
            val = key == ord('h')
            print_first_line('@u@nten @o@ben @r@echts @l@inks')
            update_cursor()
            while True:
                key = scr.getch()
                if key == ord('r'):
                    if x+1 < field.size_x:
                        field.set_v_wall(y, x+1, val)
                    break
                elif key == ord('l'):
                    if x > 0:
                        field.set_v_wall(y, x, val)
                    break
                if key == ord('o'):
                    if y+1 < field.size_y:
                        field.set_h_wall(y+1, x, val)
                    break
                elif key == ord('u'):
                    if y > 0:
                        field.set_h_wall(y, x, val)
                    break
        elif key == ord('l'):
            discs = field.get_discs(y, x)
            if discs < 9:
                field.set_discs(y, x, discs+1)
        elif key == ord('w'):
            discs = field.get_discs(y, x)
            if discs > 0:
                field.set_discs(y, x, discs-1)
        elif key == ord('v'):
            scr.addstr(0, 0, f'{"Materialvorrat des Roboters eingeben":<80}')
            scr.move(field.panel_y + 12, field.panel_x + 2)
            digits = []
            for _ in range(2):
                while True:
                    key = scr.getch()
                    if key in [ord(str(i)) for i in range(0, 10)]:
                        scr.addstr(chr(key))
                        digits.append(int(chr(key)))
                        break
            field.vorrat = digits[0] * 10 + digits[1]
        else:
            pass
    curses.curs_set(0)
    scr.clear()


def run_print_first_line():
    print_first_line(
        f'@ESC + - 0@                                                    Geschwindigkeit: {speed}'
    )


def run_program():
    global speed
    global field

    orig_field = copy.deepcopy(field)

    try:
        compile(program, 'None', 'exec')
    except SyntaxError as e:
        draw_frame(5, 60, 16, 10)
        scr.move(18, 12)
        print_highlight(f'@FEHLER!@ Syntaxfehler in Zeile {e.lineno}')
        key = scr.getch()
        scr.clear()
        return
    scr.clear()
    field.zustand = True
    field.draw()

    print_last_line('Geschwindigkeit eingeben (0..9)')
    print_first_line(f'{"Geschwindigkeit:  ":>79}')
    scr.move(0, 78)
    curses.curs_set(1)
    while True:
        key = scr.getch()
        if key in [ord(str(i)) for i in range(0, 10)]:
            speed = int(chr(key))
            break
    curses.curs_set(0)
    print_last_line('')

    run_print_first_line()
    error = False
    try:
        wait()
        exec(program, {k: v for k, v in globals().items()
                       if k in ['vor', 'drehe_links', 'nimm_auf', 'gib_ab', 'vorne_frei',
                                'links_frei', 'rechts_frei', 'hat_vorrat', 'platz_belegt']})
    except KeyboardInterrupt:
        pass
    except NikiError:
        error = True
    except NameError as e:
        line = traceback.extract_tb(sys.exc_info()[2])[-1].lineno
        print_first_line(f'@FEHLER!@ Unbekannter Name "{e.name}" in Zeile {line}')
        error = True
    if error:
        field.zustand = False
        field.draw()
        print_last_line(
            'Niki hat sich abgeschaltet                                  <Leertaste drücken>'
        )
    else:
        print_last_line(
            'Programm beendet                                            <Leertaste drücken>'
        )

    while True:
        key = scr.getch()
        if key == ord(' '):
            break
    field = orig_field
    scr.clear()


def main_menu():
    global program
    global field

    field = Field(10, 15, 1)
    robot_dialog = RobotDialog(7)
    field_dialog = FieldDialog(11)
    file_dialog = FileDialog(15, 'py')
    active_dialog = robot_dialog

    def draw():
        header = """
oo    o  o  o  o  o    oooo    ooo   oooo    ooo   ooooo  ooooo  oooo
o o   o  o  o o   o    o   o  o   o  o   o  o   o    o    o      o   o
o  o  o  o  oo    o    oooo   o   o  oooo   o   o    o    ooooo  oooo
o   o o  o  o o   o    o  o   o   o  o   o  o   o    o    o      o  o
o    oo  o  o  o  o    o   o   ooo   oooo    ooo     o    ooooo  o   o
"""[1:].replace('o', '█').splitlines()
        draw_frame(7, 80)
        for i, h in enumerate(header):
            scr.addstr(i+1, 5, h)
        robot_dialog.draw()
        field_dialog.draw()
        file_dialog.draw()

    draw()
    while True:
        CMD = active_dialog.run()
        if CMD == 'SWITCH':
            active_dialog.set_selected(-1)
            active_dialog = robot_dialog if active_dialog is field_dialog else field_dialog
            if active_dialog is robot_dialog:
                file_dialog.set_extension('py')
            else:
                file_dialog.set_extension('rob')
            draw()
        elif CMD == 'LOAD':
            old_filename = active_dialog.filename.txt
            filename = active_dialog.filename.edit('')
            if filename is None:
                continue
            if not filename:
                filename = file_dialog.run()
                if filename is None:
                    active_dialog.filename.txt = old_filename
                    active_dialog.draw()
                    continue
                active_dialog.filename.txt = filename
                active_dialog.draw()
            if active_dialog is robot_dialog:
                filename = filename + '.py'
            else:
                filename = filename + '.rob'
            if not os.path.exists(filename):
                active_dialog.filename.txt = ''
                continue
            if active_dialog is robot_dialog:
                with open(filename, 'rt') as f:
                    program = f.read()
            else:
                with open(filename, 'rb') as f:
                    field = pickle.load(f)
                    field.name = filename
        elif CMD == 'SAVE':
            filename = active_dialog.filename.edit()
            if filename is None:
                continue
            if active_dialog is robot_dialog:
                filename = filename + '.py'
            else:
                filename = filename + '.rob'
            if active_dialog is robot_dialog:
                with open(filename, 'wt') as f:
                    f.write(program)
            else:
                with open(filename, 'wb') as f:
                    pickle.dump(field, f)
            file_dialog.set_extension(file_dialog.extension)
            draw()
        elif CMD == 'EDIT':
            if active_dialog is robot_dialog:
                _teardown()
                p = subprocess.run(['micro', '-tabstospaces', 'true', '-filetype', 'python'],
                                   input=program.encode(),
                                   capture_output=True)
                program = p.stdout.decode()
                _setup()
                draw()
            else:
                edit_field()
                draw()
        elif CMD == 'NEW':
            if active_dialog is field_dialog:
                field = Field(10, 15, 1)
                edit_field()
                draw()
        elif CMD == 'RUN':
            run_program()
            draw()
        elif CMD == 'QUIT':
            break

def run():
    path = pathlib.Path.home() / 'pyniki'
    path.mkdir(exist_ok=True)
    os.chdir(path)
    _setup()
    main_menu()


if __name__ == '__main__':
    run()
