import os

from rbtools.api.utilities import RBUtilities

BLANK = 0
USER_ADDED = '#user added settings:'
COMMENT = '#'


class Settings(object):
    """Handles rbtools settings

    responsible for loading settings, as well as adding new settings.
    Order of settings and blank lines are kept when loading and saving.
    Comments (denoted by #) are allowed on blank lines, and after settings
    Settings are stored <name> <tab> <value>. Names cannot contain spaces,
    tabs or #. values (which can be strings, ints, floats, or bools) can
    contain anything except for #. Values will be converted to the correct
    type if that type is accepted.
    """
    cwd = os.getcwd()
    cwd = cwd if ('rbtools/rbtools' in cwd) else cwd + '/rbtools'
    CONFIG_FILE = cwd + '/config.dat'

    util = None
    config_file = None
    settings = None
    settings_comment = None
    ordered = None
    none_added = None

    def __init__(self, util=RBUtilities(), config_file=CONFIG_FILE):
        super(Settings, self).__init__()
        self.util = util
        self.config_file = config_file
        self.settings = {}
        self.settings_comment = {}
        self.ordered = []
        self.load()
        self.none_added = True

    def load(self):
        """loads the settings file"""
        if os.path.isfile(self.config_file):
            file = open(self.config_file, 'r')

            if file < 0:
                util.raise_error('UnknownFileError', \
                    'Could not open file: ' + config_file)

            self.settings = {}
            self.settings_comment = {}
            self.ordered = []

            line = file.readline()
            while line:
                line = line.strip()

                #filter out blank lines
                if len(line):

                    #handle comments
                    tuple = line.split(COMMENT)

                    if len(tuple[0]) == 0:  # just comment
                        self.ordered.append(COMMENT + tuple[1])
                    else:
                        comment = None
                        if len(tuple) > 1:  # inline comment
                            comment = ''

                            for i in range(1, len(tuple)):
                                comment += COMMENT + tuple[i]

                        tuple = tuple[0].split()

                        #validate setting
                        if len(tuple) < 2:
                            self.util.raise_warning('Invalid_Type', \
                                'could not read setting: ' + line)
                        else:
                            setting = tuple[1]

                            if len(tuple) > 2:  # setting had spaces

                                for i in range(2, len(tuple)):
                                    setting += ' ' + tuple[i]

                            #convert the value to the correct type
                            dec = setting.split('.')
                            if setting.isdigit():
                                setting = int(setting)
                            elif len(dec) == 2 and dec[0].isdigit() \
                                    and dec[1].isdigit():
                                setting = float(setting)
                            elif setting is 'True':
                                setting = True
                            elif setting is 'False':
                                setting = False

                            #store comment
                            name = tuple[0]
                            self.ordered.append(name)
                            self.settings[name] = setting

                            if comment:
                                self.settings_comment[name] = comment
                else:
                    self.ordered.append(BLANK)

                line = file.readline()

            file.close()

    def save(self):
        """saves the current settings"""
        keys = self.settings.keys()

        file = open(self.config_file, 'w')

        if file < 0:
            self.util.raise_error('UnknownFileError', \
                    'Could not open file: ' + config_file)

        for key in self.ordered:
            if key is BLANK:
                file.write('\n')
            elif key[0] == COMMENT:
                file.write(key + '\n')
            else:
                file.write(key + '\t' + self.settings[key])

                if key in self.settings_comment:
                    file.write('\t' + self.settings_comment[key] + '\n')
                else:
                    file.write('\n')

        file.close()

    def change_setting(self, name, value, comment=None):
        """changes the value of a setting"""

        if not name in self.settings:
            self.util.raise_warning('UnrecognizedSetting', 'Setting "' \
                + name + '" does not exist. Adding it in and setting it to "' \
                + value + '"')
            self.add_setting(name, value, comment)
        else:
            self.settings[name] = value

            if comment:
                self.settings_comment[name] = COMMENT + comment

            self.save()

    def add_setting(self, name, value, comment=None):
        """adds a setting to the settings"""
        if name in self.settings:
            self.util.raise_warning('DuplicateSetting', 'Setting "' + name + \
                '" already exists. Changing its value to "' + value + '"')
            self.change_setting(name, value, comment)
        else:
            self.settings[name] = value

            file = open(self.config_file, 'a')

            if file < 0:
                self.util.raise_error('UnknownFileError', \
                    'Could not open file: ' + config_file)

            if self.none_added:  # first user added comment (this session)
                file.write('\n' + USER_ADDED + '\n')
            self.none_added = False

            file.write(name + '\t' + value)

            if comment:
                comment = COMMENT + comment
                self.settings_comment[name] = comment
                file.write('\t' + comment + '\n')
            else:
                file.write('\n')

            file.close()

    def remove_setting(self, name):
        """removes a setting"""
        if name not in self.settings:
            self.util.raise_warning('UnkownSetting', 'Setting "' + name + \
                'does not exist')

        del self.settings[name]
        self.save()

    def get_setting(self, name):
        """returns a setting"""
        value = None

        if name not in self.settings:
            self.util.raise_warning('UnkownSetting', 'Setting "' + name + \
                'does not exist')
        else:
            value = self.settings[name]

        return value

    def set_server_url(self, value):
        self.change_setting('server_url', value)

    def set_api_uri(self, value):
        self.change_setting('api_extension', value)

    def set_cookie_file(self, value):
        self.change_setting('cookie', value)

    def get_server_url(self):
        return self.get_setting('server_url')

    def get_api_uri(self):
        return self.get_setting('api_extension')

    def get_cookie_file(self):
        return self.get_setting('cookie')
