About RBTools
=============

RBTools is a set of command line tools and a rich Python API for use with
[Review Board](https://www.reviewboard.org/).

These tools make it easy to post changes for review, keep them up-to-date,
land reviewed changes, and test other people's changes in your own tree,
check your workload, and much more.

When using RBTools, you'll do most everything through the
[rbt](https://www.reviewboard.org/docs/rbtools/latest/#rbt-command) command,
which supports a number of
[sub-commands](https://www.reviewboard.org/docs/rbtools/latest/rbt/commands/),
like [post](https://www.reviewboard.org/docs/rbtools/latest/rbt/commands/post/#rbt-post),
[diff](https://www.reviewboard.org/docs/rbtools/latest/rbt/commands/diff/#rbt-diff),
[land](https://www.reviewboard.org/docs/rbtools/latest/rbt/commands/land/#rbt-land),
and [patch](https://www.reviewboard.org/docs/rbtools/latest/rbt/commands/patch/#rbt-patch).


Installing RBTools
------------------

We provide native installers for Windows and MacOS, along with Python
packages for Linux and other platforms. See the
[RBTools Downloads](https://www.reviewboard.org/downloads/rbtools/) page
for downloads and installation instructions.

See the
[RBTools documentation](https://www.reviewboard.org/docs/rbtools/latest/) for
more information.


Using the Python API
--------------------

The included Python API can be used to write scripts and applications that
interface with Review Board, and can also be used to write new commands
for RBTools.

There's very little that you can't do with the Python API. To learn more,
see the
[RBTools Python API documentation](https://www.reviewboard.org/docs/rbtools/latest/api/)
and the [Review Board API documentation](https://www.reviewboard.org/docs/manual/latest/webapi/).


Getting Support
---------------

We can help you get going with Review Board and RBTools, and diagnose any
issues that may come up. There are two levels of support: Public community
support, and private premium support.

The public community support is available on our main
[discussion list](http://groups.google.com/group/reviewboard/). We generally
respond to requests within a couple of days. This support works well for
general, non-urgent questions that don't need to expose confidential
information.

We can also provide more
[dedicated, private support](https://www.beanbaginc.com/support/contracts/) for
your organization through a support contract. We offer same-day responses
(generally within a few hours, if not sooner), confidential communications,
installation/upgrade assistance, emergency database repair, phone/chat (by
appointment), priority fixes for urgent bugs, and backports of urgent fixes to
older releases (when possible).


Our Happy Users
---------------

There are thousands of companies and organizations using Review Board and
RBTools today. We respect the privacy of our users, but some of them have
asked to feature them on the [Happy Users
page](https://www.reviewboard.org/users/).

If you're using Review Board, and you're a happy user,
[let us know!](https://groups.google.com/group/reviewboard/)


Reporting Bugs
--------------

Hit a bug? Let us know by
[filing a bug report](https://www.reviewboard.org/bugs/new/).

You can also look through the
[existing bug reports](https://www.reviewboard.org/bugs/) to see if anyone else
has already filed the bug.


Contributing
------------

Are you a developer? Do you want to integrate with RBTools, or work on RBTools
itself? Great! Let's help you get started.

First off, read through our
[contributor guide](https://www.reviewboard.org/docs/codebase/dev/).

We accept patches to Review Board, RBTools, and other related projects on
[reviews.reviewboard.org](https://reviews.reviewboard.org/). (Please note that
we do not accept pull requests.)

Got any questions about anything related to RBTools and development? Head
on over to our
[development discussion list](https://groups.google.com/group/reviewboard-dev/).


### Testing RBTools

If you're writing patches for RBTools, you'll need to know how to run our
test suite.

First, make sure you have the necessary dependencies:

```
$ ./setup.py develop
$ pip install -r dev-requirements.txt
```


#### Running the Tests

Running the test suite is easy. Simply run:

```
$ ./tests/runtests.py
```

from the top of the source tree. You can also run a particular set of tests.
For instance:

```
$ ./tests/runtests.py rbtools.api.tests
```

See `./tests/runtests.py --help` for more options.


Related Projects
----------------

* [Review Board](https://github.com/reviewboard/reviewboard/) -
  Our powerful, open source code review tool.
* [Djblets](https://github.com/djblets/djblets/) -
  Our pack of Django utilities for datagrids, API, extensions, and more. Used
  by Review Board.
* [Review Bot](https://www.reviewboard.org/downloads/reviewbot/) -
  Pluggable, automated code review for Review Board.
* [RB Gateway](https://www.reviewboard.org/downloads/rbgateway/) -
  Manages Git repositories, providing a full API enabling all of Review Board's
  feaures.
