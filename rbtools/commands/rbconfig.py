import os
from optparse import OptionParser

from rbtools.utils.filesystem import load_config_files


def main():
    parser = OptionParser(prog='rb config', usage='%prog',
                          description='Show user configuration.')
    parser.add_option('-a', '--all', action='store_true',
                      help='show all values (by default, only string '
                           'constants are shown)')
    opt, args = parser.parse_args()

    config, configs = load_config_files(os.getcwd())
    width = max([len(s) for s in config])

    for name in config:
        if opt.all or isinstance(config[name], str):
            print '%-*s : %s' % (width, name, config[name])


if __name__ == "__main__":
    main()
