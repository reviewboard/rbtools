=====================
RBTools Documentation
=====================

RBTools is a set of command line tools for working with `Review Board`_ and
RBCommons_. It's there to help quickly get your code up for review, check on
the status of changes, and eventually land your code in the codebase,
amongst other uses.

RBTools interfaces with your repository's official command line tools, making
it easy to generate suitable diffs or to apply changes across any supported
type of repository without having to learn different sets of tools.

Along with a variety of helpful commands, RBTools also provides a powerful
Python client API for Review Board, giving you the flexibility to develop your
own integrations.

.. _`Review Board`: https://www.reviewboard.org/
.. _RBCommons: https://rbcommons.com/


What's in RBTools
=================

.. _rbt:

rbt Command
-----------

All the RBTools commands are invoked through the :command:`rbt` tool. This
runs on Windows, Linux, and MacOS X, and contains a number of useful
sub-commands through the following usage::

   $ rbt <command> [options] [<args>]

You can get help on :command:`rbt` or a sub-command in the following ways::

   $ rbt help
   $ rbt help <command>
   $ rbt <command> --help

Some of the most commonly-used commands include:

* :ref:`rbt-post` - Posts changes to Review Board
* :ref:`rbt-diff` - Displays the diff that will be sent to Review Board
* :ref:`rbt-land` - Lands a change in a local branch or on a review request
* :ref:`rbt-patch` - Patches your tree with a change on a review request
* :ref:`rbt-setup-repo` - Sets up RBTools to talk to your repository

There are many other commands you may find useful. See the
:ref:`full list of commands <rbt-commands>`.


Python API
----------

RBTools provides a Python module makes it easy to communicate with any Review
Board server using its powerful REST API. You can write custom scripts or even
new RBTools command that can attach metadata to review requests, perform
reviews, analyze diffs, extract analytics data, or almost anything else.

There's a lot you can do with the API. See the :ref:`rbtools-api`
documentation for more information.


Installation
============

To install RBTools, simply visit the `RBTools Downloads`_ page and follow the
instructions for your operating system. If you are using MacOS X or Windows,
just run the installer and you'll be set.

.. _`RBTools Downloads`: https://www.reviewboard.org/downloads/rbtools/

If you're using Microsoft's Team Foundation Server, there's some extra
:ref:`installation or configuration <rbtools-tfs>` that may be necessary.


Configuration
=============

Once you've installed RBTools, you'll want to configure it to
:ref:`work with your repositories <rbtools-repo-config>`. This is the first
step to allow any of your developers to easily post changes using RBTools.

There's also a number of
:ref:`user-configurable options <rbtools-user-config>` as well, including
customizable defaults for parameters and
:ref:`custom aliases <rbtools-aliases>` for common operations or sets of
flags. Auto-completions are also available and can be installed by using the
command :ref:`rbt setup-completion <rbt-setup-completion>`.


Indices, Glossary and Tables
============================

* :ref:`glossary`


.. toctree::
   :hidden:

   rbt/index
   api/index
   glossary
