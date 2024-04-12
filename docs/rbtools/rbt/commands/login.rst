.. rbt-command:: rbtools.commands.login.Login

=====
login
=====

.. versionchanged:: 5.0
   The login command can now direct the user to log in via the Review Board
   web page, instead of prompting for a username and password in the terminal.

If :rbtconfig:`WEB_LOGIN` is set in :file:`.reviewboardrc` or the
:option:`--web` option is passed, :command:`rbt login` will direct the user to
log in via the Review Board web page. Otherwise, the user will be prompted for
a username and password in the terminal. A session cookie will be saved in
:file:`.rbtools-cookies` upon successful authentication.

A username and password can also be directly supplied through the
:option:`--username` and :option:`--password` options.

Or, an API token can be used to log in with the :option:`--api-token` option.


.. rbt-command-usage::
.. rbt-command-options::
