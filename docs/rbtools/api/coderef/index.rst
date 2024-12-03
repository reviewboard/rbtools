.. _rbtools-coderef:

===========================
Module and Class References
===========================


Top-Level Modules
=================

.. autosummary::
   :toctree: python

   rbtools
   rbtools.deprecation


Review Board API
================

.. autosummary::
   :toctree: python

   rbtools.api
   rbtools.api.cache
   rbtools.api.capabilities
   rbtools.api.client
   rbtools.api.decode
   rbtools.api.decorators
   rbtools.api.errors
   rbtools.api.factory
   rbtools.api.request
   rbtools.api.resource
   rbtools.api.transport
   rbtools.api.transport.sync
   rbtools.api.utils


Source Code Management Clients
==============================

Base Support
------------

.. autosummary::
   :toctree: python

   rbtools.clients
   rbtools.clients.base
   rbtools.clients.base.patch
   rbtools.clients.base.registry
   rbtools.clients.base.repository
   rbtools.clients.base.scmclient
   rbtools.clients.errors


Client Implementations
----------------------

.. autosummary::
   :toctree: python

   rbtools.clients.bazaar
   rbtools.clients.clearcase
   rbtools.clients.cvs
   rbtools.clients.git
   rbtools.clients.mercurial
   rbtools.clients.perforce
   rbtools.clients.plastic
   rbtools.clients.sos
   rbtools.clients.svn
   rbtools.clients.tfs


RBTools Configuration
---------------------

.. autosummary::
   :toctree: python

   rbtools.config
   rbtools.config.config
   rbtools.config.loader


Diff Generation/Processing/Patching
-----------------------------------

.. autosummary::
   :toctree: python

   rbtools.diffs
   rbtools.diffs.patches
   rbtools.diffs.patcher
   rbtools.diffs.tools
   rbtools.diffs.tools.backends
   rbtools.diffs.tools.backends.gnu
   rbtools.diffs.tools.base
   rbtools.diffs.tools.base.diff_file_result
   rbtools.diffs.tools.base.diff_tool
   rbtools.diffs.tools.errors
   rbtools.diffs.tools.registry
   rbtools.diffs.writers


RBTools Commands
================

Base Support
------------

.. autosummary::
   :toctree: python

   rbtools.commands
   rbtools.commands.main



Base Command Support
--------------------

.. autosummary::
   :toctree: python

   rbtools.commands
   rbtools.commands.base
   rbtools.commands.base.commands
   rbtools.commands.base.errors
   rbtools.commands.base.options
   rbtools.commands.base.output


Command Implementations
-----------------------

.. autosummary::
   :toctree: python

   rbtools.commands.alias
   rbtools.commands.api_get
   rbtools.commands.attach
   rbtools.commands.clearcache
   rbtools.commands.close
   rbtools.commands.diff
   rbtools.commands.info
   rbtools.commands.install
   rbtools.commands.land
   rbtools.commands.list_repo_types
   rbtools.commands.login
   rbtools.commands.logout
   rbtools.commands.patch
   rbtools.commands.post
   rbtools.commands.publish
   rbtools.commands.review
   rbtools.commands.setup_completion
   rbtools.commands.setup_repo
   rbtools.commands.stamp
   rbtools.commands.status
   rbtools.commands.status_update


Repository Hooks
================

Base Support
------------

.. autosummary::
   :toctree: python

   rbtools.hooks
   rbtools.hooks.common


Repository Implementations
--------------------------

.. autosummary::
   :toctree: python

   rbtools.hooks.git


Testing
=======

.. autosummary::
   :toctree: python

   rbtools.testing
   rbtools.testing.api
   rbtools.testing.api.payloads
   rbtools.testing.api.transport
   rbtools.testing.commands
   rbtools.testing.testcase
   rbtools.testing.transport


Utilities
=========

.. autosummary::
   :toctree: python

   rbtools.utils
   rbtools.utils.aliases
   rbtools.utils.browser
   rbtools.utils.checks
   rbtools.utils.commands
   rbtools.utils.console
   rbtools.utils.diffs
   rbtools.utils.encoding
   rbtools.utils.errors
   rbtools.utils.filesystem
   rbtools.utils.graphs
   rbtools.utils.mimetypes
   rbtools.utils.process
   rbtools.utils.repository
   rbtools.utils.review_request
   rbtools.utils.source_tree
   rbtools.utils.users
