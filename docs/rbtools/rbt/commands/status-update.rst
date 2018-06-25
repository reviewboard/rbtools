.. rbt-command:: rbtools.commands.status_update.StatusUpdate

=============
status-update
=============

:command:`rbt status-update` is used to interact with status-updates for review
requests. There are three sub-commands for interacting with status-updates on
review requests: ``get``, ``set``, ``delete``.

.. rbt-command-usage::

Getting status-updates
======================

:command:`rbt status-update --review-request-id ID get` is used for getting all
status-updates associated with the review request specified or, if the
:option:`--status-update-id` option is specified, then only the status-update
specified that is associated to the review request.

Setting status-updates
======================

:command:`rbt status-update --review-request-id ID set` is used for creating
and updating status-updates. The :option:`--review` option can be used to pass
in a JSON formatted file with review details to attach a review to the
status-update.

Deleting status-updates
=======================

:command:`rbt status-update --review-request-id ID --status-update-id ID delete`
is used for deleting status-updates.

.. rbt-command-options::

:option:`--json` is a flag for having the output of the command be formatted in
JSON.

:option:`--review` is for adding a review with the status-update. This option
is for specifying a file describing the review and comments for the review.
An example of the contents for the file::

    {
        "review": {
            "body_top": "Header comment"
        },
        "diff_comments": [
            {
                "filediff_id": 1,
                "first_line": 1,
                "issue_opened": true,
                "num_lines": 1,
                "text": "Adding a comment on a diff line",
                "text_type": "markdown"
            },
            {
                "filediff_id": 2,
                "first_line": 2,
                "issue_opened": true,
                "num_lines": 1,
                "text": "Adding a second diff comment",
                "text_type": "markdown"
            }
        ],
        "general_comments": [
            {
                "text": "Adding a general comment",
                "text_type": "markdown"
            }
        ]
    }

