Aliases
=======

.. _rbtools-aliases:

:command:`rbt` can be configured to add command aliases. The ``ALIASES`` value
in :file:`.reviewboardrc` can be added to allow for command aliasing. It is a
dictionary where the keys are the alias names and the value is the command
that will be executed.

Aliases will only be executed when an :command:`rbt` command is executed that
:command:`rbt` does not recognize and when ``rbt-<commandname>`` does not exist
in the path. Aliases are case-sensitive.

For example, consider the following aliases:

.. code-block:: python

    ALIASES = {
        'post-this': 'post HEAD',
        'push': '!git push && rbt close $1'
    }


The following commands are equivalent::

    $ rbt post-this
    $ rbt post HEAD

As are the following::

    $ rbt push 3351
    $ git push && rbt close 3351



Types of Aliases
----------------

There are two types of aliases: aliases for other :command:`rbt` commands and
system aliases.


Aliases For Other :command:`rbt` Commands
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

These aliases allow short forms for frequently used :command:`rbt` commands
with parameter substitution. An alias of the form ``cmd`` is equivalent to
calling ``rbt cmd``. This will launch another instance of :command:`rbt` and
therefore can be used to reference other aliases or commands of the form
``rbt-<commandname>``.


System Command Aliases
~~~~~~~~~~~~~~~~~~~~~~

System aliases are aliases that begin with ``!``. These aliases are more
flexible because they are executed by the shell. However, since they are more
powerful it is possible to write an alias that will *destroy data*. Everything
after the ``!`` will be passed to the shell for execution after going through
parameter substitution.


Positional Parameter Substitution
---------------------------------

Aliases in :command:`rbt` supports inserting bash-like variables representing
positional arguments into aliases. Positional variables take the form ``$1``
(which corresponds to the first argument), ``$2`` (which corresponds to the
second argument), etc., and ``$*`` (which corresponds to *all* arguments).

If a positional variable is specified and not enough arguments were specified,
it will be replaced with an empty argument.

If no parameter substitution is performed, all supplied arguments will be
appended to the command when it is executed. Non-numeric variables are not
replaced in the parameter and, if the alias is a system command alias, will be
handled by the shell.
