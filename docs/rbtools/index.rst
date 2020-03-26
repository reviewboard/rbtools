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

The "rbt" Command
-----------------

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
* :ref:`rbt-setup-completion` - Set up shell integration/auto-completion
* :ref:`rbt-stamp` - Stamp a local commit with a review request URL
* :ref:`rbt-status-update` - Register or update a "status update" on a review
  request, for automatic code review


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
instructions for your operating system.

.. _`RBTools Downloads`: https://www.reviewboard.org/downloads/rbtools/

.. admonition:: Using Microsoft Team Foundation Server?

   You will need to install and configure some additional tools as well. See
   the our guide on :ref:`configuring TFS <rbtools-tfs>`.


Configuration
=============

Repositories
------------

Once you've installed RBTools, you'll want to configure it to work with each
of your repositories. This is done with a :file:`.reviewboardrc` file. This is
the first step to allow any of your developers to easily post changes using
RBTools.

* :ref:`Configure your repositories <rbtools-repo-config>`


User Environments
-----------------

There's a number of options available to RBTools users, from command line
argument defaults to custom aliases and shell integration. We've broken this
into multiple guides:

* :ref:`Configurable options and environment variables <rbtools-user-config>`
* :ref:`Creating custom aliases <rbtools-aliases>`
* :ref:`Shell integration/auto-completion <rbt-setup-completion>`


Indices, Glossary and Tables
============================

* :ref:`glossary`


.. toctree::
   :hidden:

   rbt/index
   api/index
   glossary
