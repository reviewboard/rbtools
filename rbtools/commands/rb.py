import os
import re
import sys

from rbtools.commands import *
from rbtools.api.utilities import RBUtilities
#from rbtools.api.temputilities import execute
import __init__


def main():
    valid = False

    if len(sys.argv) > 1:
        util = RBUtilities()

        # Check if the first parameter is a rb-<name>.py file in this dir
        pattern = re.compile('(rb-%s){1}(?!.)' % sys.argv[1])
        for n in __init__.__all__:
            if pattern.match(n) and not valid:
                valid = True
                cmd_list = ['python', 'rb-%s.py' % sys.argv[1]] + sys.argv[2:]
                print util.execute(cmd_list)

    if not valid:
        print "usage: rb COMMAND [OPTIONS] [ARGS]"
        print ""
        print "The commands available are:"
        pattern = re.compile('(rb-)')

        for n in __init__.__all__:
            sp = re.split('rb-', n)
            if len(sp) > 1:
                print sp[1]

if __name__ == "__main__":
    main()
