import curses
import sys
from contextlib import contextmanager

_curs_state = None
_scr = None


class SizeError(Exception):
    pass


def setup():
    global _scr
    global _curs_state
    _scr = curses.initscr()
    _curs_state = curses.curs_set(0)

    y, x = _scr.getmaxyx()
    if y < 25 or x < 80:
        raise SizeError

    curses.noecho()
    curses.cbreak()
    try:
        curses.set_escdelay(1)
    except AttributeError:
        pass
    _scr.keypad(True)
    _scr.clear()


def teardown():
    curses.nocbreak()
    _scr.keypad(False)
    curses.echo()
    curses.curs_set(_curs_state)
    curses.endwin()


class ScrWrapper():
    def __getattr__(self, name):
        return getattr(_scr, name)

scr = ScrWrapper()


@contextmanager
def curses_setup():
    try:
        setup()
    except SizeError:
        teardown()
        print('Terminalfenster zu klein!')
        sys.exit(1)

    try:
        yield
    finally:
        teardown()


@contextmanager
def curses_disabled():
    teardown()
    try:
        yield
    finally:
        setup()
