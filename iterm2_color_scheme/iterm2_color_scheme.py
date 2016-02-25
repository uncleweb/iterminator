#!/usr/bin/env python
from collections import deque
from threading import Thread
from time import sleep
import argparse
import os
import readline
import random
import subprocess
import sys

from getch import getch


class Scheme(object):
    """
    An iTerm2 color scheme.
    """
    def __init__(self, path):
        self.path = path

    @property
    def name(self):
        return os.path.basename(self.path).split('.')[0]

    def __repr__(self):
        return self.name


class ColorSchemeSelector(object):
    """
    An interactive iTerm2 color scheme selector.
    """
    # Animation control keys
    PAUSE = {' '}
    NEXT = {'j'}
    PREV = {'k'}
    QUIT = {'\r', '\x03'}  # return, ctrl-c

    def __init__(self):
        self.repo_dir = os.path.join(os.path.dirname(__file__),
                                     'iTerm2-Color-Schemes')
        schemes_dir = self.repo_dir + '/schemes'
        self.schemes = deque(
            Scheme(os.path.join(schemes_dir, scheme_file))
            for scheme_file in os.listdir(schemes_dir)
            if scheme_file.endswith('.itermcolors')
        )
        self.name_to_scheme = {s.name: s for s in self.schemes}
        self.scheme_names = [s.name for s in self.schemes]
        self.blank = ' ' * max(len(s.name) for s in self.schemes)

        self.animation_control = Thread(target=self.animation_control)
        self.paused = False
        self.quitting = False

        readline.set_completer(self.complete)
        readline.set_completer_delims('')
        readline.parse_and_bind('tab: complete')
        readline.parse_and_bind('set completion-ignore-case on')
        readline.parse_and_bind('set completion-query-items -1')
        readline.parse_and_bind('set show-all-if-ambiguous on')
        readline.parse_and_bind('"\e[C": menu-complete')
        readline.parse_and_bind('"\e[D": menu-complete-backward')

    @property
    def scheme(self):
        return self.schemes[0]

    def next(self):
        self.schemes.rotate(-1)

    def prev(self):
        self.schemes.rotate(+1)

    def goto(self, scheme):
        # TODO O(1)
        while self.scheme != scheme:
            self.next()

    def shuffle(self):
        random.shuffle(self.schemes)
        self.scheme_names = [s.name for s in self.schemes]

    def apply(self):
        """
        Apply current scheme to current iTerm2 session.
        """
        subprocess.check_call([
            self.repo_dir + '/tools/preview.rb',
            self.scheme.path,
        ])

    def display_scheme(self):
        sys.stdout.write('\r%s\r%s' % (self.blank, self.scheme))
        sys.stdout.flush()

    def animate(self, animate_interval, shuffle):
        if shuffle:
            self.shuffle()
        self.animation_control.start()
        self.schemes.rotate(+1)
        while True:
            if self.quitting:
                self.quit()
            elif self.paused:
                sleep(0.1)
            else:
                self.schemes.rotate(-1)
                self.apply()
                self.display_scheme()
                sleep(animate_interval)

    def animation_control(self):
        while True:
            char = getch()
            if char in self.PAUSE:
                self.paused = not self.paused
            elif char in self.NEXT:
                self.next()
                self.apply()
                self.display_scheme()
            elif char in self.PREV:
                self.prev()
                self.apply()
                self.display_scheme()
            elif char in self.QUIT:
                self.quitting = True
                break

    def quit(self):
        self.animation_control.join()
        print
        sys.exit(0)

    def select(self):
        """
        Select a color theme interactively.
        """
        while True:
            try:
                self.goto(self.name_to_scheme[raw_input()])
            except KeyboardInterrupt:
                print
                sys.exit(0)
            except KeyError:
                sys.exit(1)
            else:
                self.apply()

    def complete(self, text, state):
        """
        Return state'th completion for current input.

        This is the standard readline completion function.
        https://docs.python.org/2/library/readline.html

        text: the current input
        state: an integer specifying which of the matches for the current input
               should be returned
        """
        if state == 0:
            # First call for current input; compute and cache completions
            if text:
                self.current_matches = self.get_matches(text)

                if len(self.current_matches) == 1:
                    # Unique match; apply scheme and return the completion
                    [completion] = self.current_matches
                    self.goto(self.name_to_scheme[completion])
                    self.apply()
                    return completion
            else:
                self.current_matches = self.scheme_names
        try:
            completion = self.current_matches[state]
        except IndexError:
            completion = None

        return completion

    def get_matches(self, text):
        """
        Return matches for current readline input.
        """
        if text.endswith('$'):
            text = text[:-1]
            if text in self.name_to_scheme:
                return [text]
            else:
                return []
        else:
            return [
                name
                for name in self.scheme_names
                if text.lower() in name.lower()
            ]


def main():
    if os.getenv('TMUX'):
        error(
            "Please detach from your tmux session before running this command."
        )

    selector = ColorSchemeSelector()
    arg_parser = argparse.ArgumentParser(
        description=(
            "Color theme selector for iTerm2.\n\n"
            "With no arguments, the command runs in interactive mode: use tab "
            "to complete color scheme names (other standard readline key "
            "bindings are also available)."),
        epilog=(
            "The color schemes are from "
            "https://github.com/mbadolato/iTerm2-Color-Schemes, which is "
            "included as a git submodule in this project. All credit for the "
            "schemes goes to the original scheme authors and to the "
            "iTerm2-Color-Schemes project. To add a new scheme, please first "
            "create a pull request against iTerm2-Color-Schemes to add your "
            "scheme, and then open a pull request or issue against "
            "https://github.com/dandavison/iterm2-color-scheme to update the "
            "submodule."),
        formatter_class=argparse.RawTextHelpFormatter,
    )

    arg_parser.add_argument(
        '-a', '--animate',
        nargs='?',
        type=float,
        const=1.0,
        help=("Cycle through color schemes automatically "
              "(optionally followed by pause duration in seconds)\n"
              "The following keys are available in animation mode:\n"
              "space - pause/unpause\n\n"),
    )

    arg_parser.add_argument(
        '-l', '--list',
        action='store_true',
        help="List available color schemes",
    )

    arg_parser.add_argument(
        '-q', '--quiet',
        action='store_true',
        help="Don't display initial key bindings help message",
    )

    arg_parser.add_argument(
        '-r', '--random',
        action='store_true',
        help="Select a random color scheme"
    )

    arg_parser.add_argument(
        '-s', '--scheme',
        help="Available choices are\n%s" % ' | '.join(selector.scheme_names),
    )

    args = arg_parser.parse_args()

    if args.animate:

        try:
            selector.animate(args.animate, args.random)
        except KeyboardInterrupt:
            print
            sys.exit(0)

    elif args.list:

        for scheme in selector.schemes:
            print scheme

    elif args.random:

        selector.shuffle()
        selector.apply()
        print selector.scheme

    elif args.scheme:

        names = selector.get_matches(args.scheme)
        if len(names) == 0:
            error("No matches")
        elif len(names) == 1:
            [name] = names
            scheme = selector.name_to_scheme[name]
            selector.goto(scheme)
            selector.apply()
            print selector.scheme
        elif len(schemes) > 1:
            error("Multiple matches: %s" % ', '.join(schemes))

    else:

        if not args.quiet:
            print 'Tab to complete color scheme names'
        selector.select()


def error(msg):
    print >>sys.stderr, msg
    sys.exit(1)


if __name__ == '__main__':
    main()
