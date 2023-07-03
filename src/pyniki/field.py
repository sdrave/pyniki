import curses

from pyniki.curses import scr
from pyniki.ui import print_first_line


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
        scr.addstr(panel_y + 2, panel_x, self.name)
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


def edit_field(field):
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
