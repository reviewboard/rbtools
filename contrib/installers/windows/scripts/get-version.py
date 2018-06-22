from __future__ import print_function, unicode_literals

from rbtools import VERSION


# MSI files only use the first 3 version fields, and has no concept of
# alphas/betas/RCs/patch levels.
if VERSION[2] == 0:
    print('%s.%s' % VERSION[:2])
else:
    print('%s.%s.%s' % VERSION[:3])
