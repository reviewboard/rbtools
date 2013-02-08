from optparse import OptionParser
from rbtools.utils.filesystem import get_config_value
from rbtools import get_version_string

def get_script_option_parser(configs):
    parser = OptionParser(usage="%prog [-pond] [-r review_id] [changenum]",
                          version="RBTools " + get_version_string())

    parser.add_option("-p", "--publish",
                      dest="publish", action="store_true",
                      default=get_config_value(configs, 'PUBLISH', False),
                      help="publish the review request immediately after "
                           "submitting")
    parser.add_option("-r", "--review-request-id",
                      dest="rid", metavar="ID", default=None,
                      help="existing review request ID to update")
    parser.add_option("-o", "--open",
                      dest="open_browser", action="store_true",
                      default=get_config_value(configs, 'OPEN_BROWSER', False),
                      help="open a web browser to the review request page")
    parser.add_option("-n", "--output-diff",
                      dest="output_diff_only", action="store_true",
                      default=False,
                      help="outputs a diff to the console and exits. "
                           "Does not post")
    parser.add_option("--server",
                      dest="server",
                      default=get_config_value(configs, 'REVIEWBOARD_URL'),
                      metavar="SERVER",
                      help="specify a different Review Board server to use")
    parser.add_option("--disable-proxy",
                      action='store_true',
                      dest='disable_proxy',
                      default=not get_config_value(configs, 'ENABLE_PROXY',
                                                   True),
                      help="prevents requests from going through a proxy "
                           "server")
    parser.add_option("--diff-only",
                      dest="diff_only", action="store_true", default=False,
                      help="uploads a new diff, but does not update "
                           "info from changelist")
    parser.add_option("--reopen",
                      dest="reopen", action="store_true", default=False,
                      help="reopen discarded review request "
                           "after update")
    parser.add_option("--target-groups",
                      dest="target_groups",
                      default=get_config_value(configs, 'TARGET_GROUPS'),
                      help="names of the groups who will perform "
                           "the review")
    parser.add_option("--target-people",
                      dest="target_people",
                      default=get_config_value(configs, 'TARGET_PEOPLE'),
                      help="names of the people who will perform "
                           "the review")
    parser.add_option("--summary",
                      dest="summary", default=None,
                      help="summary of the review ")
    parser.add_option("--description",
                      dest="description", default=None,
                      help="description of the review ")
    parser.add_option("--description-file",
                      dest="description_file", default=None,
                      help="text file containing a description of the review")
    parser.add_option('-g', '--guess-fields',
                      dest="guess_fields", action="store_true",
                      default=get_config_value(configs, 'GUESS_FIELDS',
                                               False),
                      help="equivalent to --guess-summary --guess-description")
    parser.add_option("--guess-summary",
                      dest="guess_summary", action="store_true",
                      default=get_config_value(configs, 'GUESS_SUMMARY',
                                               False),
                      help="guess summary from the latest commit (git/"
                           "hg/hgsubversion only)")
    parser.add_option("--guess-description",
                      dest="guess_description", action="store_true",
                      default=get_config_value(configs, 'GUESS_DESCRIPTION',
                                               False),
                      help="guess description based on commits on this branch "
                           "(git/hg/hgsubversion only)")
    parser.add_option("--testing-done",
                      dest="testing_done", default=None,
                      help="details of testing done ")
    parser.add_option("--testing-done-file",
                      dest="testing_file", default=None,
                      help="text file containing details of testing done ")
    parser.add_option("--branch",
                      dest="branch",
                      default=get_config_value(configs, 'BRANCH'),
                      help="affected branch ")
    parser.add_option("--bugs-closed",
                      dest="bugs_closed", default=None,
                      help="list of bugs closed ")
    parser.add_option("--change-description", default=None,
                      help="description of what changed in this revision of "
                           "the review request when updating an existing request")
    parser.add_option("--revision-range",
                      dest="revision_range", default=None,
                      help="generate the diff for review based on given "
                           "revision range")
    parser.add_option("--submit-as",
                      dest="submit_as",
                      default=get_config_value(configs, 'SUBMIT_AS'),
                      metavar="USERNAME",
                      help="user name to be recorded as the author of the "
                           "review request, instead of the logged in user")
    parser.add_option("--username",
                      dest="username",
                      default=get_config_value(configs, 'USERNAME'),
                      metavar="USERNAME",
                      help="user name to be supplied to the reviewboard "
                           "server")
    parser.add_option("--password",
                      dest="password",
                      default=get_config_value(configs, 'PASSWORD'),
                      metavar="PASSWORD",
                      help="password to be supplied to the reviewboard server")
    parser.add_option("--change-only",
                      dest="change_only", action="store_true",
                      default=False,
                      help="updates info from changelist, but does "
                           "not upload a new diff (only available if your "
                           "repository supports changesets)")
    parser.add_option("--parent",
                      dest="parent_branch",
                      default=get_config_value(configs, 'PARENT_BRANCH'),
                      metavar="PARENT_BRANCH",
                      help="the parent branch this diff should be against "
                           "(only available if your repository supports "
                           "parent diffs)")
    parser.add_option("--tracking-branch",
                      dest="tracking",
                      default=get_config_value(configs, 'TRACKING_BRANCH'),
                      metavar="TRACKING",
                      help="Tracking branch from which your branch is derived "
                           "(git only, defaults to origin/master)")
    parser.add_option("--p4-client",
                      dest="p4_client",
                      default=get_config_value(configs, 'P4_CLIENT'),
                      help="the Perforce client name that the review is in")
    parser.add_option("--p4-port",
                      dest="p4_port",
                      default=get_config_value(configs, 'P4_PORT'),
                      help="the Perforce servers IP address that the review "
                           "is on")
    parser.add_option("--p4-passwd",
                      dest="p4_passwd",
                      default=get_config_value(configs, 'P4_PASSWD'),
                      help="the Perforce password or ticket of the user "
                           "in the P4USER environment variable")
    parser.add_option('--svn-changelist', dest='svn_changelist', default=None,
                      help='generate the diff for review based on a local SVN '
                           'changelist')
    parser.add_option("--repository-url",
                      dest="repository_url",
                      default=get_config_value(configs, 'REPOSITORY'),
                      help="the url for a repository for creating a diff "
                           "outside of a working copy (currently only "
                           "supported by Subversion with --revision-range or "
                           "--diff-filename and ClearCase with relative "
                           "paths outside the view). For git, this specifies"
                           "the origin url of the current repository, "
                           "overriding the origin url supplied by the git "
                           "client.")
    parser.add_option("-d", "--debug",
                      action="store_true", dest="debug",
                      default=get_config_value(configs, 'DEBUG', False),
                      help="display debug output")
    parser.add_option("--diff-filename",
                      dest="diff_filename", default=None,
                      help='upload an existing diff file, instead of '
                           'generating a new diff')
    parser.add_option('--http-username',
                      dest='http_username',
                      default=get_config_value(configs, 'HTTP_USERNAME'),
                      metavar='USERNAME',
                      help='username for HTTP Basic authentication')
    parser.add_option('--http-password',
                      dest='http_password',
                      default=get_config_value(configs, 'HTTP_PASSWORD'),
                      metavar='PASSWORD',
                      help='password for HTTP Basic authentication')
    return parser