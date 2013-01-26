    name = 'Git'

        # Store the 'correct' way to invoke git, just plain old 'git' by
        # default.
            if (sys.platform.startswith('win') and
                check_install('git.cmd --help')):
        self.bare = execute([self.git, "config",
                             "core.bare"]).strip() == 'true'
            git_top = execute([self.git, "rev-parse", "--show-toplevel"],
                              ignore_errors=True).rstrip("\n")

            # Top level might not work on old git version se we use git dir
            # to find it.
            if git_top.startswith("fatal:") or not os.path.isdir(git_dir):
                git_top = git_dir
            os.chdir(os.path.abspath(git_top))

        self.head_ref = execute([self.git, 'symbolic-ref', '-q',
                                 'HEAD'], ignore_errors=True).strip()
        # revisions, which can be slow. Also skip SVN detection if the git
        # repository was specified on command line.
        if (not self.options.repository_url and
            os.path.isdir(git_svn_dir) and len(os.listdir(git_svn_dir)) > 0):
                        if self.options.parent_branch:
                            self.upstream_branch = self.options.parent_branch
                            m = re.search(r'^Remote Branch:\s*(.+)$', data,
                                          re.M)
                                sys.stderr.write('Failed to determine SVN '
                                                 'tracking branch. Defaulting'
                                                 'to "master"\n')
        if self.head_ref:
            short_head = self._strip_heads_prefix(self.head_ref)
            merge = execute([self.git, 'config', '--get',
                             'branch.%s.merge' % short_head],
                            ignore_errors=True).strip()
            remote = execute([self.git, 'config', '--get',
                              'branch.%s.remote' % short_head],
                             ignore_errors=True).strip()

            merge = self._strip_heads_prefix(merge)
            if remote and remote != '.' and merge:
                self.upstream_branch = '%s/%s' % (remote, merge)
        if self.options.repository_url:
            url = self.options.repository_url
            self.upstream_branch = self.get_origin(self.upstream_branch, True)[0]
            # Central bare repositories don't have origin URLs.
            # We return git_dir instead and hope for the best.
            if not url:
                url = os.path.abspath(git_dir)
                # There is no remote, so skip this part of upstream_branch.
                self.upstream_branch = self.upstream_branch.split('/')[-1]
        upstream_branch = (self.options.tracking or
                           default_upstream_branch or
                           'origin/master')
        return ((actual[0] > expected[0]) or
                (actual[0] == expected[0] and actual[1] > expected[1]) or
                (actual[0] == expected[0] and actual[1] == expected[1] and
                 actual[2] >= expected[2]))
        parent_branch = self.options.parent_branch
        head_ref = "HEAD"
        if self.head_ref:
            head_ref = self.head_ref
        self.merge_base = execute([self.git, "merge-base",
                                   self.upstream_branch,
                                   head_ref]).strip()
            diff_lines = self.make_diff(self.merge_base, head_ref)
        if self.options.guess_summary and not self.options.summary:
            s = execute([self.git, "log", "--pretty=format:%s", "HEAD^.."],
                              ignore_errors=True)
            self.options.summary = s.replace('\n', ' ').strip()
        if self.options.guess_description and not self.options.description:
            self.options.description = execute(
            diff_lines = execute([self.git, "diff", "--no-color",
                                  "--no-prefix", "--no-ext-diff", "-r", "-u",
                                  rev_range],
            cmdline = [self.git, "diff", "--no-color", "--full-index",
                       "--no-ext-diff", "--ignore-submodules", "--no-renames",
                       rev_range]

            if (self.capabilities is not None and
                self.capabilities.has_capability('diffs', 'moved_files')):
                cmdline.append('-M')

            return execute(cmdline)
                # Add the following so that we know binary files were
                # added/changed.
        head_ref = "HEAD"
        if self.head_ref:
            head_ref = self.head_ref

        self.merge_base = execute([self.git, "merge-base",
                                   self.upstream_branch,
                                   head_ref]).strip()
                parent_diff_lines = self.make_diff(self.merge_base,
                                                   revision_range)

            if self.options.guess_summary and not self.options.summary:
                s = execute([self.git, "log", "--pretty=format:%s",
                             revision_range + ".."], ignore_errors=True)
                self.options.summary = s.replace('\n', ' ').strip()

            if (self.options.guess_description and
                not self.options.description):
                self.options.description = execute(
                    [self.git, "log", "--pretty=format:%s%n%n%b",
                     revision_range + ".."],
            if self.options.guess_summary and not self.options.summary:
                s = execute([self.git, "log", "--pretty=format:%s",
                             "%s..%s" % (r1, r2)], ignore_errors=True)
                self.options.summary = s.replace('\n', ' ').strip()
            if (self.options.guess_description and
                not self.options.description):
                self.options.description = execute(
                    [self.git, "log", "--pretty=format:%s%n%n%b",
                     "%s..%s" % (r1, r2)],