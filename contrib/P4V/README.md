P4V Custom Tools for RBTools
============================

This directory contains custom tools for integrating RBTools into
[P4V](https://www.perforce.com/downloads/helix-visual-client-p4v). Once
installed, you can right-click on a changeset and post it for review to Review
Board.


Installation
------------

1. Make sure that `p4` and `rbt` are available in your system path.

   You may need to restart P4V if it was opened when installing RBTools.

2. Download the correct P4V configuration for your configuration:

    **Windows:**
    [P4V-Windows-RBTools-Install.xml](P4V-Windows-RBTools-Install.xml)

    **macOS / Linux:**
    [P4V-Mac-Linux-Tools-Import.xml](P4V-Mac-Linux-Tools-Import.xml)

3. In P4V, go to **Tools -> Manage Tools -> Custom Tools** and click
   **Import Custom Tools...**

4. Select the downloaded file and confirm.

You should now be set!


**Note:** These configurations are defaults. Depending on your system, you may
have to adjust the paths in your custom tools (found in **Tools -> Manage Tools
-> Custom Tools**).


Usage
-----

1. Right-click a change to post for review.

2. Click **Review Board - Post for Review**.

   This can be used to create a new review request or update an existing one.

3. A browser window should open to the review request.

For more information, see [Using RBTools with Perforce](https://www.reviewboard.org/docs/rbtools/latest/workflows/perforce/).
