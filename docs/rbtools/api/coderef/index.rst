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

Base Support
------------

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
   rbtools.api.transport
   rbtools.api.transport.sync
   rbtools.api.utils


Resource Base Classes
---------------------

.. autosummary::
   :toctree: python

   rbtools.api.resource
   rbtools.api.resource.base
   rbtools.api.resource.base_archived_object
   rbtools.api.resource.base_comment
   rbtools.api.resource.base_diff_commit
   rbtools.api.resource.base_review_group
   rbtools.api.resource.base_review_request
   rbtools.api.resource.base_review
   rbtools.api.resource.base_user
   rbtools.api.resource.mixins


Resources
---------

.. autosummary::
   :toctree: python

   rbtools.api.resource.api_token
   rbtools.api.resource.archived_review_request
   rbtools.api.resource.change
   rbtools.api.resource.default_reviewer
   rbtools.api.resource.diff_comment
   rbtools.api.resource.diff_commit
   rbtools.api.resource.diff_context
   rbtools.api.resource.diff_file_attachment
   rbtools.api.resource.diff
   rbtools.api.resource.draft_diff_commit
   rbtools.api.resource.draft_file_attachment
   rbtools.api.resource.draft_screenshot
   rbtools.api.resource.extension
   rbtools.api.resource.file_attachment_comment
   rbtools.api.resource.file_attachment
   rbtools.api.resource.file_diff
   rbtools.api.resource.general_comment
   rbtools.api.resource.hosting_service_account
   rbtools.api.resource.hosting_service
   rbtools.api.resource.last_update
   rbtools.api.resource.muted_review_request
   rbtools.api.resource.oauth_application
   rbtools.api.resource.oauth_token
   rbtools.api.resource.plain_text
   rbtools.api.resource.remote_repository
   rbtools.api.resource.repository_branch
   rbtools.api.resource.repository_commit
   rbtools.api.resource.repository_group
   rbtools.api.resource.repository_info
   rbtools.api.resource.repository_user
   rbtools.api.resource.repository
   rbtools.api.resource.review_group_user
   rbtools.api.resource.review_group
   rbtools.api.resource.review_reply
   rbtools.api.resource.review_request_draft
   rbtools.api.resource.review_request
   rbtools.api.resource.review
   rbtools.api.resource.root
   rbtools.api.resource.screenshot_comment
   rbtools.api.resource.screenshot
   rbtools.api.resource.search
   rbtools.api.resource.server_info
   rbtools.api.resource.session
   rbtools.api.resource.status_update
   rbtools.api.resource.user_file_attachment
   rbtools.api.resource.user
   rbtools.api.resource.validate_diff_commit
   rbtools.api.resource.validate_diff
   rbtools.api.resource.validation
   rbtools.api.resource.watched_review_group
   rbtools.api.resource.watched_review_request
   rbtools.api.resource.watched
   rbtools.api.resource.webhook



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
