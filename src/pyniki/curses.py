import curses
from contextlib import contextmanager

_curs_state = None
_scr = None

def setup():
    global _scr
    global _curs_state
    _scr = curses.initscr()

    _curs_state = curses.curs_set(0)
    curses.noecho()
    curses.cbreak()
    curses.set_escdelay(1)
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
    setup()
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
