from __future__ import unicode_literals


# This file provides a Mercurial extension that resets certain
# config options to provide consistent output.

# We use reposetup because the config is re-read for each repo, after
# uisetup() is called.
ALLOWED_PARAMS = ['git', 'svn']


def reposetup(ui, repo):
    for section in ['diff']:
        for k, v in ui.configitems(section):
            # Setting value to None is effectively unsetting the value since
            # None is the stand-in value for "not set."
            if k not in ALLOWED_PARAMS:
                ui.setconfig(section, k, None)
