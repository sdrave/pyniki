import curses
import glob
import os
import pathlib
import pickle
import subprocess

from pyniki.curses import curses_disabled, curses_setup, scr
from pyniki.field import Field, edit_field
from pyniki.sim import run_program
from pyniki.ui import draw_frame, print_last_line


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
            # Word(y+2, 10, 'Compile', True),
            Word(y+2, 23, 'Run', True),
            Word(y+2, 34, 'New', True),
            Word(y+2, 44, 'Load', True),
            Word(y+2, 54, 'Save', True),
            # Word(y+2, 64, 'Print', True),
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
            # Word(y+2, 10, 'Handsteuerung', True),
            Word(y+2, 34, 'New', True),
            Word(y+2, 44, 'Load', True),
            Word(y+2, 54, 'Save', True),
            # Word(y+2, 64, 'Print', True),
            Word(y+2, 74, 'Quit', True),
        ]
        self.filename = FileName(self.y+1, 14)
        self.selected = -1


    def draw(self):
        super().draw()
        scr.addstr(self.y+1, 1, 'Roboterfeld:')


class MainMenu:

    def __init__(self):
        self.program = None
        self.field = None
        self.robot_dialog = RobotDialog(7)
        self.field_dialog = FieldDialog(11)
        self.file_dialog = FileDialog(15, 'py')

    def draw(self):
        header = """
oo    o  o  o  o  o     oooo    ooo   oooo    ooo   ooooo  ooooo  oooo
o o   o  o  o o   o     o   o  o   o  o   o  o   o    o    o      o   o
o  o  o  o  oo    o     oooo   o   o  oooo   o   o    o    ooooo  oooo
o   o o  o  o o   o     o  o   o   o  o   o  o   o    o    o      o  o
o    oo  o  o  o  o     o   o   ooo   oooo    ooo     o    ooooo  o   o
"""[1:].replace('o', '█').splitlines()
        draw_frame(7, 80)
        for i, h in enumerate(header):
            scr.addstr(i+1, 5, h)
        self.robot_dialog.draw()
        self.field_dialog.draw()
        self.file_dialog.draw()

    def save_program(self):
        filename = self.robot_dialog.filename.txt + '.py'
        with open(filename, 'wt') as f:
            f.write(self.program)

    def save_field(self):
        filename = self.field_dialog.filename.txt + '.rob'
        with open(filename, 'wb') as f:
            pickle.dump(self.field, f)

    def edit_program(self):
        with curses_disabled():
            p = subprocess.run(['micro', '-tabstospaces', 'true', '-filetype', 'python'],
                               input=self.program.encode(),
                               capture_output=True)
            self.program = p.stdout.decode()

    def quit_dialog(self):
        draw_frame(7, 60, 16, 10)
        scr.addstr(17, 11, 'Niki-Programm beenden (j/n)? ')
        curses.curs_set(1)
        while True:
            key = scr.getch()
            if key == ord('n'):
                scr.clear()
                self.draw()
                curses.curs_set(0)
                return False
            elif key == ord('j'):
                scr.addstr('j')
                break

        if self.program is not None:
            scr.addstr(19, 11, 'Roboterprogramm speichern (j/n)? ')
            while True:
                key = scr.getch()
                if key == ord('n'):
                    scr.addstr('n')
                    break
                elif key == ord('j'):
                    scr.addstr('j')
                    self.save_program()
                    break

        if self.field is not None:
            scr.addstr(21, 11, 'Roboterfeld speichern (j/n)? ')
            while True:
                key = scr.getch()
                if key == ord('n'):
                    scr.addstr('n')
                    break
                elif key == ord('j'):
                    scr.addstr('j')
                    self.save_field()
                    break

        return True

    def run(self):
        robot_dialog, field_dialog, file_dialog = self.robot_dialog, self.field_dialog, self.file_dialog
        active_dialog = robot_dialog
        self.draw()
        while True:
            CMD = active_dialog.run()
            if CMD == 'SWITCH':
                active_dialog.set_selected(-1)
                active_dialog = robot_dialog if active_dialog is field_dialog else field_dialog
                if active_dialog is robot_dialog:
                    file_dialog.set_extension('py')
                else:
                    file_dialog.set_extension('rob')
                self.draw()
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
                        self.program = f.read()
                else:
                    with open(filename, 'rb') as f:
                        self.field = pickle.load(f)
                        self.field.name = field_dialog.filename.txt
            elif CMD == 'SAVE':
                if active_dialog is robot_dialog:
                    if self.program is None:
                        continue
                else:
                    if self.field is None:
                        continue
                filename = active_dialog.filename.edit()
                if filename is None:
                    continue
                if active_dialog is robot_dialog:
                    self.save_program()
                else:
                    self.save_field()
                file_dialog.set_extension(file_dialog.extension)
                self.draw()
            elif CMD == 'EDIT':
                if not active_dialog.filename.txt:
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
                    if self.program is None:
                        self.program = ''
                    self.edit_program()
                    self.draw()
                else:
                    if self.field is None:
                        self.field = Field(10, 15, 1, name=self.field_dialog.filename.txt)
                    edit_field(self.field)
                    self.draw()
            elif CMD == 'NEW':
                active_dialog.filename.txt = 'NONAME'
                if active_dialog is robot_dialog:
                    self.program = ''
                    self.edit_program()
                else:
                    self.field = Field(10, 15, 1, name=self.field_dialog.filename.txt)
                    edit_field(self.field)
                self.draw()
            elif CMD == 'RUN':
                if self.program is None:
                    print_last_line(
                        'Es wurde noch keine Datei geladen                           <Leertaste drücken>'
                    )
                    while scr.getch() != ord(' '):
                        pass
                    print_last_line('')
                    continue
                if self.field is None:
                    print_last_line(
                        'Es wurde noch kein Arbeitsfeld geladen                      <Leertaste drücken>'
                    )
                    while scr.getch() != ord(' '):
                        pass
                    print_last_line('')
                    continue
                run_program(self.program, self.field)
                self.draw()
            elif CMD == 'QUIT':
                if self.quit_dialog():
                    break


def run():
    path = pathlib.Path.home() / 'pyniki'
    path.mkdir(exist_ok=True)
    os.chdir(path)
    with curses_setup():
        MainMenu().run()


if __name__ == '__main__':
    run()
