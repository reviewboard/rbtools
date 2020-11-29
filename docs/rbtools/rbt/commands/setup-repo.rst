.. rbt-command:: rbtools.commands.setup_repo.SetupRepo

==========
setup-repo
==========

.. versionadded:: 0.5.3

:command:`rbt setup-repo` will interactively configure your repository to point
to a Review Board server by generating or overwriting the configuration file
:file:`.reviewboardrc` in the current working directory.


.. rbt-command-usage::


.. _rbt-setup-repo-configuring-repositories:

Configuring repositories on your server
=======================================

Prior to running ``setup-repo``, ensure that your repositories are configured
on the Review Board server you wish to connect to. RBTools will not find
repositories that have not been added to the server.

If you are an RBCommons_ customer, you can add repositories under your team
administration settings. If you are managing your own deployment of Review
Board, refer to the Admin Dashboard. :ref:`Learn more about configuring
repositories <rb:repositories>`.


Setting up your server
======================

If :rbtconfig:`REVIEWBOARD_URL` is not defined in your
:ref:`rbtools-reviewboardrc`, you will be prompted to enter the URL of a valid
Review Board server you want to connect to. Alternatively, you may use
:option:`--server` to skip this prompt.

Note that if you use RBCommons, you will need to verify your RBCommons
credentials first.


Selecting a repository
======================

If RBTools finds multiple repositories in your Review Board server, you can
select which repository you want to use. If no repositories are found,
this means that you currently have no repositories configured on your server
(see :ref:`configuring repositories on your server
<rbt-setup-repo-configuring-repositories>`).

When you select a repository, you will be prompted to confirm the repository
of your choice, as well as any changes to your current ``.reviewboardrc``
configuration file. Confirming will generate or update your ``.reviewboardrc``
with information related to your chosen repository.


After generating ``.reviewboardrc``
===================================

Thanks to your newly generated ``.reviewboardrc`` file, you can now use
RBTools to communicate between your chosen repository and your Review
Board server.


.. rbt-command-options::

.. _RBCommons: https://rbcommons.com/
