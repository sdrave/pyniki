import curses

from pyniki.curses import scr


def draw_frame(height, width, offset_y=0, offset_x=0, active=False):
    attr = curses.A_BOLD if active else curses.A_NORMAL
    scr.addstr(offset_y, offset_x,
               '╒' + '═' * (width-2) + '╕', attr)
    for i in range(height-2):
        scr.addstr(offset_y+i+1, offset_x,
                   '│' +  ' ' * (width-2) + '│', attr)
    scr.addstr(offset_y+height-1, offset_x,
               '╘' + '═' * (width-2) + '╛', attr)


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


