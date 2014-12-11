from __future__ import print_function, unicode_literals

from rbtools import VERSION


# MSI files only use the first 3 version fields, and has no concept of
# alphas/betas/RCs/patch levels.
print('%s.%s.%s' % (VERSION[0], VERSION[1], VERSION[2]))
