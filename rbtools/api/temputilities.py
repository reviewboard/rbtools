import os
import sys
import subprocess


def execute(command, env=None, split_lines=False, \
        ignore_errors=False, extra_ignore_errors=(), translate_newlines=True):
        """
        if isinstance(command, list):
            self.output(subprocess.list2cmdline(command))
        else:
            self.output(command)
        """

        if env:
            env.update(os.environ)
        else:
            env = os.environ.copy()

        env['LC_ALL'] = 'en_US.UTF-8'
        env['LANGUAGE'] = 'en_US.UTF-8'

        print "running: %s" % command

        if sys.platform.startswith('win'):
            p = subprocess.Popen(command)
            """,
                                 stdin=subprocess.PIPE,
                                 stdout=subprocess.PIPE,
                                 stderr=subprocess.STDOUT,
                                 shell=False,
                                 universal_newlines=translate_newlines,
                                 env=env)
            """
        else:
            p = subprocess.Popen(command)
            """
                                 stdin=subprocess.PIPE,
                                 stdout=subprocess.PIPE,
                                 stderr=subprocess.STDOUT,
                                 shell=False,
                                 close_fds=True,
                                 universal_newlines=translate_newlines,
                                 env=env)
            """
#        if split_lines:
#            print p.stdout.readlines()
#        else:
#            print p.stdout.read()

        #rc = p.wait()

        #if rc and not ignore_errors and rc not in extra_ignore_errors:
        #    print('Failed to execute command: %s\n%s' % (command, data))

        #return data
