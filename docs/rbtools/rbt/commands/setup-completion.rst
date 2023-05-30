.. rbt-command:: rbtools.commands.setup_completion.SetupCompletion

================
setup-completion
================

.. versionadded:: 1.0

:command:`rbt setup-completion` helps generate scripts that can add
auto-completion of RBTools commands to your shell. This allows you to
tab-complete RBTools commands. For example:

.. code-block:: console

   $ rbt p<tab>
   patch          post           publish

Auto-completion scripts are outputted to the terminal, allowing you to either
copy/paste them into your shell configuration or pipe them to a file.

This currently supports Bash and Zsh shells. You can optionally specify either
``bash`` or ``zsh`` as a parameter to get the appropriate script. By default,
the correct script for your current shell will be used.


.. versionchanged:: 5.0
   Previous versions of RBTools attempted to write these scripts to known
   directories automatically, but that was too error-prone for most
   configurations.


.. rbt-command-usage::


Installing Completion Scripts
=============================

Bash
----

1. Determine where you want your completion script to go.

   You have a few options for where to place your auto-completion script.

   * :file:`~/.bashrc`
   * :file:`~/.local/share/bash-completion/completions/rbt`
   * :file:`/usr/share/bash-completion/completions/rbt`
   * :file:`/etc/bash_completion.d/rbt`

   The correct path depends on your version of Bash, your operating system
   environment, and your local configuration. If in doubt, you can just place
   these in :file:`~/.bashrc`

   If you place it in a completions directory, make sure the file is named
   :file:`rbt`.

2. Generate a script for Bash:

   .. code-block:: console

      $ rbt setup-completion bash

   You can copy/paste from this, or output it directly to the path you prefer.

3. Restart your shell and type ``rbt <tab>`` to test that it worked.


Zsh
---

1. Determine where you want your completion script to go.

   To see where completion files are stored, run:

   .. code-block:: console

      $ echo $fpath

   You can place the completion file (named :file:`_rbt`) in any of these
   paths.

   To specify a custom path, add the following to your :file:`~/.zshrc`:

   .. code-block:: shell

      fpath=(/path/to/completionsdir $fpath)

2. Make sure auto-completion is enabled for your shell.

   Your shell configuration should enable ``compinit`` by including the
   following line:

   .. code-block:: shell

      autoload -U compinit && compinit

   If you're using Oh-My-Zsh, this should be enabled for you.

3. Generate a script for Zsh:

   .. code-block:: console

      $ rbt setup-completion zsh

   You can copy/paste from this, or output it directly to the path you prefer.

4. Restart your shell and type ``rbt <tab>`` to test that it worked.


.. rbt-command-options::
