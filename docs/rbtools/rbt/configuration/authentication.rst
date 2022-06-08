.. _rbtools-authentication:

==============================
Authenticating to Review Board
==============================

Most RBTools commands require authenticating to a Review Board server. If you
are not currently logged in, RBTools will prompt you to do so.


Login Sessions
==============

When running a command which requires authenticating with the server, RBTools
will prompt you for your username and password. You can also do this explicitly
by running :command:`rbt login`.

After logging in, your session will be stored in the :file:`.rbtools-cookies`
file. Depending on how the server is set up, these sessions will periodically
expire.

.. admonition:: Using Single Sign-On?

   When Review Board is configured to use Single Sign-On, you may not have a
   password to use to log in with RBTools. In this case, you'll need to
   authenticate using API Tokens.


Using API Tokens
================

Instead of a username and password, RBTools can authenticate to the server
using an API token. This has the additional benefit that tokens can be limited
in their scope, and can be individually created and revoked as necessary.

API Tokens can be created inside Review Board by selecting :guilabel:`My
Account`, and then choosing :guilabel:`Authentication`. See
:ref:`Creating API Tokens <rb:api-tokens>` for details.

After you have an API token, you can either pass it to :command:`rbt login`, or
you can store it in your personal :file:`.reviewboardrc` file.

.. code-block:: console

    $ rbt login --api-token <token>

In :file:`.reviewboardrc`::

    API_TOKEN = "<token>"
