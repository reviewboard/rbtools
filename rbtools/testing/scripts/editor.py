#!/usr/bin/env python
#
# Fake editor script used for unit tests. This will convert all content to
# uppercase.

import sys


filename = sys.argv[1]

with open(filename, 'r') as fp:
    content = fp.read()

with open(filename, 'w') as fp:
    fp.write(content.upper())
