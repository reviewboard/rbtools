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

Let's explore RBTools:

* :ref:`What's in RBTools? <whats-in-rbtools>`
* :ref:`Getting started <rbtools-getting-started>`
* :ref:`Common RBTools workflows <rbtools-workflows-summary>`


.. _Review Board: https://www.reviewboard.org/
.. _RBCommons: https://rbcommons.com/


.. _whats-in-rbtools:

What's in RBTools?
==================

.. _rbt:

The "rbt" Command
-----------------

All the RBTools commands are invoked through the :command:`rbt` tool. This
runs on Windows, Linux, and MacOS X, and contains a number of useful
sub-commands through the following usage:

.. code-block:: console

   $ rbt <command> [options] [<args>]

You can get help on :command:`rbt` or a sub-command in the following ways:

.. code-block:: console

   $ rbt help
   $ rbt help <command>
   $ rbt <command> --help

Some of the most commonly-used commands include:

* :ref:`rbt-post` - Posts changes to Review Board
* :ref:`rbt-diff` - Displays the diff that will be sent to Review Board
* :ref:`rbt-land` - Lands a change in a local branch or on a review request
* :ref:`rbt-patch` - Patches your tree with a change on a review request
* :ref:`rbt-setup-repo` - Sets up RBTools to talk to your repository
* :ref:`rbt-status` - Display the status of your outgoing review requests

There's a whole suite of additional commands that might also be useful:

* :ref:`rbt-alias` - Create custom aliases for commands and operations
* :ref:`rbt-api-get` - Retrieve structured information from the API
* :ref:`rbt-attach` - Upload and attach files to a review request
* :ref:`rbt-clear-cache` - Clear your local RBTools caches
* :ref:`rbt-close` - Close a review request
* :ref:`rbt-install` - Install special components for third-party integrations
* :ref:`rbt-list-repo-types` - List all repository types supported by RBTools
* :ref:`rbt-login` - Create a Review Board login session for RBTools
* :ref:`rbt-logout` - Log RBTools out of Review Board
* :ref:`rbt-publish` - Publish a review request
* :ref:`rbt-review` - Create and publish reviews
* :ref:`rbt-setup-completion` - Set up shell integration/auto-completion
* :ref:`rbt-stamp` - Stamp a local commit with a review request URL
* :ref:`rbt-status-update` - Register or update a "status update" on a review
  request, for automatic code review

:ref:`Learn more about RBTools commands <rbt>`.


The RBTools Python API
----------------------

RBTools isn't just a set of commands. It's also a platform for writing your
own code, including:

* Custom :command:`rbt` commands
* Automation scripts for Review Board
* Analytics tools
* New automated code review integrations
* Repository hooks and triggers

And more.

Using the :ref:`RBTools Python API <rbtools-api>`, you can write programs that
talk to the :ref:`Review Board API <rb:webapiguide>` or to your local source
code management system, all from Python.

:ref:`Learn more about the RBTools Python API <rbtools-api>`.


.. _rbtools-getting-started:

Getting Started
===============

We'll walk you through getting RBTools ready to use with Review Board.

1. :ref:`Install RBTools <rbtools-installation>`.

   Steps are provided all major operating systems and Linux distributions.

2. :ref:`Authenticate with Review Board <rbtools-authentication>`.

3. :ref:`Configure RBTools for your repositories <rbtools-repo-config>`.

   RBTools configuration lives in a :file:`.reviewboardrc` file, which is
   usually stored in your source code repository, so everyone can share the
   same configuration.

   This is the first step to allow any of your developers to easily post
   changes using RBTools.

4. Optionally, customize your RBTools experience:

   * :ref:`Configure options and environment variables <rbtools-user-config>`
   * :ref:`Creating custom command aliases <rbtools-aliases>`
   * :ref:`Enable shell integration and auto-completion
     <rbt-setup-completion>`

   These can also live in a separate :file:`.reviewboardrc` in your home
   directory, letting you make your RBTools experience your own.


.. _rbtools-workflows-summary:

Common RBTools Workflows
========================

Every source code management system is different. We have guides on the most
common workflows to help you get started:

* :ref:`rbtools-workflow-sos`
* :ref:`rbtools-workflow-git`
* :ref:`rbtools-workflow-versionvault`
* :ref:`rbtools-workflow-perforce`


.. toctree::
   :hidden:

   installation
   rbt/index
   workflows/index
   api/index
   glossary
