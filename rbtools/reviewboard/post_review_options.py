import logging
import os
import re

class PostReviewOptions(object):
    def __init__(self, opts):
        self._options = opts

    def __getattr__(self, attrib):
        return getattr(self._options, attrib)

    def process_request(self, review_request, server):
        if self._options.target_groups:
            server.set_review_request_field(review_request, 'target_groups', self._options.target_groups)

        if self._options.target_people:
            server.set_review_request_field(review_request, 'target_people', self._options.target_people)

        if self._options.summary:
            server.set_review_request_field(review_request, 'summary', self._options.summary)

        if self._options.branch:
            server.set_review_request_field(review_request, 'branch', self._options.branch)

        if self._options.bugs_closed:     # append to existing list
            self._options.bugs_closed = self._options.bugs_closed.strip(", ")
            bug_set = set(re.split("[, ]+", self._options.bugs_closed)) | \
                      set(review_request['bugs_closed'])
            self._options.bugs_closed = ",".join(bug_set)
            server.set_review_request_field(review_request, 'bugs_closed', self._options.bugs_closed)

        if self._options.description:
            server.set_review_request_field(review_request, 'description', self._options.description)

        if self._options.testing_done:
            server.set_review_request_field(review_request, 'testing_done', self._options.testing_done)

        if self._options.change_description:
            server.set_review_request_field(review_request, 'changedescription', self._options.change_description)

    def validate(self):
        if self._options.debug:
            logging.getLogger().setLevel(logging.DEBUG)

        if self._options.description and self._options.description_file:
            return "The --description and --description-file options are mutually exclusive.\n"

        if self._options.description_file:
            if os.path.exists(self._options.description_file):
                fp = open(self._options.description_file, "r")
                self._options.description = fp.read()
                fp.close()
            else:
                return "The description file %s does not exist.\n" % self._options.description_file

        if self._options.guess_fields:
            self._options.guess_summary = True
            self._options.guess_description = True

        if self._options.testing_done and self._options.testing_file:
            return "The --testing-done and --testing-done-file options are mutually exclusive.\n"

        if self._options.testing_file:
            if os.path.exists(self._options.testing_file):
                fp = open(self._options.testing_file, "r")
                self._options.testing_done = fp.read()
                fp.close()
            else:
                return "The testing file %s does not exist.\n" % self._options.testing_file

        if self._options.reopen and not self._options.rid:
            return "The --reopen option requires --review-request-id option.\n"

        if self._options.change_description and not self._options.rid:
            return "--change-description may only be used when updating an existing review-request\n"