.. rbt-command:: rbtools.commands.setup_completion.SetupCompletion

================
setup-completion
================

.. versionadded:: 0.8

:command:`rbt setup-completion` currently supports Bash and Zsh for
auto-completions. The command will detect your login shell and install the
appropriate auto-completions for your shell. You can also specify which
auto-completions you wish to install by replacing `<shell>` with either
`bash` or `zsh`.


.. rbt-command-usage::


Please refer to the installation notes for OS X and Linux if you are having
difficulties running the command.


Installation Notes
------------------

OS X
~~~~

Zsh gets installed in a directory that requires root permission to write to.
You can either run the command as root or follow the instructions for manual
installation below. To install, run::

	$ sudo rbt setup-completion zsh

Note: Bash on OS X does not require the use of ``sudo``.


Linux
~~~~~

Both Bash and Zsh are installed in directories that require root permission to
write to. You can either run the command as root or follow the instructions for
manual installation below. To install, run::

	$ sudo rbt setup-completion <shell>


Manual Installation
-------------------

Bash
~~~~

You will first need to download the `bash auto completion`_ file. Copy the
file to your home directory, and add the following command to your
:file:`.bash_profile` file::

	source ~/rbt-bash-completion


ZSH
~~~

You will first need to download the `zsh auto completion`_ file. Next, create a
directory in your home directory called .rbt-completion and copy the file to
~/.rbt-completion. Then add the following to your :file:`.zshrc` file::

	fpath=(~/.rbt-completion $fpath)
	autoload -U compinit && compinit


.. rbt-command-options::


.. _bash auto completion: https://github.com/reviewboard/rbtools/tree/master/rbtools/commands/conf/rbt-bash-completion
.. _zsh auto completion: https://github.com/reviewboard/rbtools/tree/master/rbtools/commands/conf/_rbt-zsh-completion
