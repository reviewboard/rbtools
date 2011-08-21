from rbtools.commands import rbconfig
from rbtools.utils.testbase import RBTestBase


class RBConfigTest(RBTestBase):
    """Test rb-config command."""
    VALUES = {'foo': 'bar', 'bar': 'bazz'}

    def _test_output(self, config, options=[]):
        self.chdir_tmp()
        self.reset_cl_args(options)

        f = open('.reviewboardrc', 'w')

        for i in config.iteritems():
            f.write('%s="%s"\n' % i)

        f.close()

        text = self.catch_output(rbconfig.main)
        values = dict([[s.strip() for s in line.split(':')]
                       for line in text.splitlines() if line])

        for name in config:
            self.assertEquals(str(config[name]), values[name])

    def test_print_strings(self):
        """Test default behaviour of rb-config."""
        self._test_output(self.VALUES)

    def test_print_all(self):
        """Test the -a/--all options in rb-config."""
        ext_values = self.VALUES.copy()
        ext_values.update({'foobar': 0xFF, 'foobaz': 42})
        self._test_output(ext_values, ['-a'])
        self._test_output(ext_values, ['--all'])
