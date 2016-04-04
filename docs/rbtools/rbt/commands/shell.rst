.. rbt-command:: rbtools.commands.shell.Shell

=====
shell
=====

:command:`rbt shell` will open a pre-configured Python shell within the shell
that runs the command.

The shell is pre-configured with a dictionary from
:file:`.reviewboardrc` configurations files and a dictionary from the command
options. The python shell can optionally be chosen with :option:`--ipython` or
:option:`--bpython` if they are installed. If :option:`--server` is provided
a client connection is made and the API client and API root are defined.

.. rbt-command-usage::
.. rbt-command-options::
