import os
import sys

from rbtools.commands import *


def main():
    if len(sys.argv) > 1:
        if sys.argv[1] == 'publish':
            if len(sys.argv) > 2:
                rbpublish.main(sys.argv[2:])
        if sys.argv[1] == 'open':
            if len(sys.argv) > 2:
                rbopen.main(sys.argv[2:])
        if sys.argv[1] == 'close':
            if len(sys.argv) > 2:
                rbclose.main(sys.argv[2:])
        elif sys.argv[1] == 'someothercommand':
            pass


if __name__ == "__main__":
    main()
