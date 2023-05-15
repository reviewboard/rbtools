"""Implementation of rbt api-get."""

import json
import re

from rbtools.api.errors import APIError
from rbtools.commands import (Command,
                              CommandError,
                              CommandExit,
                              Option,
                              ParseError)


class APIGet(Command):
    name = 'api-get'
    author = 'The Review Board Project'
    description = 'Retrieve raw API resource payloads.'

    needs_api = True

    args = '<path> [--<query-arg>=<value> ...]'
    option_list = [
        Option('--pretty',
               action='store_true',
               dest='pretty_print',
               config_key='API_GET_PRETTY_PRINT',
               default=False,
               help='Pretty prints the resulting API payload.'),
        Command.server_options,
    ]

    def _dumps(self, payload):
        if self.options.pretty_print:
            return json.dumps(payload, sort_keys=True, indent=4)
        else:
            return json.dumps(payload)

    def main(self, path, *args):
        query_args = {}
        query_arg_re = re.compile('^--(?P<name>.*)=(?P<value>.*)$')

        for arg in args:
            m = query_arg_re.match(arg)

            if m:
                query_args[m.group('name')] = m.group('value')
            else:
                raise ParseError('Unexpected query argument %s' % arg)

        try:
            if path.startswith('http://') or path.startswith('https://'):
                resource = self.api_client.get_url(path, **query_args)
            else:
                resource = self.api_client.get_path(path, **query_args)
        except APIError as e:
            if e.rsp:
                self.stdout.write(self._dumps(e.rsp))
                raise CommandExit(1)
            else:
                raise CommandError('Could not retrieve the requested '
                                   'resource: %s' % e)

        self.stdout.write(self._dumps(resource.rsp))
