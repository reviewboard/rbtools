.. rbt-command:: rbtools.commands.login.Login

=====
login
=====

.. versionchanged:: 5.0
   The login command now directs the user to log in via the Review Board web
   page, instead of prompting for a username and password in the terminal.

:command:`rbt login` will direct the user to log in via the Review Board web
page, and save a session cookie in :file:`.rbtools-cookies` upon successful
login.

A username and password can be supplied directly in the terminal by
using the :option:`--terminal` option, or the :option:`--username` and
:option:`--password` options.


.. rbt-command-usage::
.. rbt-command-options::
