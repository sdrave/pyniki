import copy
import curses
import sys
import time
import traceback

from pyniki.curses import scr
from pyniki.ui import draw_frame, print_first_line, print_highlight, print_last_line


class NikiError(Exception):
    pass


_field = None


def wait():
    global speed
    _field.draw()
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
    y, x = _field.pos
    match _field.direction:
        case 0:
            return not _field.v_walls[y][x+1]
        case 1:
            return not _field.h_walls[y+1][x]
        case 2:
            return not _field.v_walls[y][x]
        case 3:
            return not _field.h_walls[y][x]


def vorne_frei():
    return is_free(_field.direction)


def links_frei():
    return is_free((_field.direction + 1) % 4)


def rechts_frei():
    return is_free((_field.direction - 1) % 4)


def hat_vorrat():
    return _field.vorrat > 0


def platz_belegt():
    discs = _field.get_discs(*_field.pos)
    return discs > 0


def nimm_auf():
    if not platz_belegt():
        raise NikiError
    if _field.vorrat == 99:
        raise NikiError
    y, x = _field.pos
    _field.set_discs(y, x, _field.get_discs(y, x) - 1)
    _field.vorrat += 1
    wait()


def gib_ab():
    if not hat_vorrat():
        raise NikiError
    y, x = _field.pos
    discs = _field.get_discs(*_field.pos)
    if discs == 9:
        raise NikiError
    _field.set_discs(y, x, discs + 1)
    _field.vorrat -= 1
    wait()


def vor():
    if not vorne_frei():
        raise NikiError()
    y, x = _field.pos
    match _field.direction:
        case 0:
            _field.pos = [y, x+1]
        case 1:
            _field.pos = [y+1, x]
        case 2:
            _field.pos = [y, x-1]
        case 3:
            _field.pos = [y-1, x]
    wait()


def drehe_links():
    _field.direction = (_field.direction + 1) % 4
    wait()


def run_print_first_line():
    print_first_line(
        f'@ESC + - 0@                                                    Geschwindigkeit: {speed}'
    )


def run_program(program, field):
    global speed
    global _field

    _field = copy.deepcopy(field)

    try:
        compile(program, 'None', 'exec')
    except (IndentationError, SyntaxError) as e:
        draw_frame(5, 60, 16, 10)
        scr.move(18, 12)
        if isinstance(e, IndentationError):
            print_highlight(f'@FEHLER!@ Falsche Einrückung in Zeile {e.lineno}')
        else:
            print_highlight(f'@FEHLER!@ Syntaxfehler in Zeile {e.lineno}')
        key = scr.getch()
        scr.clear()
        return
    scr.clear()
    _field.zustand = True
    _field.draw()

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
        _field.zustand = False
        _field.draw()
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
    scr.clear()
