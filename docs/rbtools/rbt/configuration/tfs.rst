.. _rbtools-tfs:

====================================
Team Foundation Server Configuration
====================================

Depending on what version of Visual Studio (or other development environment)
you're using, there are different requirements for TFS. The table below
summarizes the three different methods and the different features which are
available under each.

Note that if you're running VS2017, the only option available is the built-in
tf.exe method.

+---------------------------+---------------+------------------+--------------------------+
|                           | VS2017 tf.exe | rb-tfs adaptor   | Team Explorer Everywhere |
+===========================+===============+==================+==========================+
| OS support                | Windows       | All              | All                      |
+---------------------------+---------------+------------------+--------------------------+
| Visual Studio versions    | 2017          | 2010, 2013, 2015 | 2010, 2013, 2015         |
+---------------------------+---------------+------------------+--------------------------+
| Posting pending changes   | Yes           | Yes              | Yes                      |
+---------------------------+---------------+------------------+--------------------------+
| Posting committed changes | No            | Yes              | No                       |
+---------------------------+---------------+------------------+--------------------------+
| Posting shelvesets        | No            | Yes              | No                       |
+---------------------------+---------------+------------------+--------------------------+


VS2017 tf.exe
-------------

Visual Studio 2017 includes a command-line tool, :command:`tf.exe`, which
includes enough support for RBTools to post pending changes to Review Board.
Committed changes can be posted, but only through the web UI, and shelvesets
are not supported.

Due to changes in Microsoft's data storage formats, if you're using VS2017, the
other options (the rb-tfs adaptor and Team Explorer Everywhere) will not work.

This method requires GNU diff but no other installation.


.. _rb-tfs:

rb-tfs adaptor
--------------

When using Visual Studio 2010 through 2015, the Team Explorer Everywhere tools,
or the TFS extensions for Eclipse, we provide a custom adaptor which supports
posting pending, committed, or shelved changes.

To install the rb-tfs adaptor, run:

.. code-block:: console

     $ rbt install tfs


Team Explorer Everywhere
------------------------

If you have the `Team Explorer Everywhere`_ command-line tools installed,
RBTools can use that for posting committed changes. In all cases where you
might use this, the :ref:`rb-tfs` adaptor is faster and supports more features.
Team Explorer Everywhere works with Visual Studio 2010 through 2015.

.. _`Team Explorer Everywhere`:
   https://www.visualstudio.com/en-us/products/team-explorer-everywhere-vs.aspx
