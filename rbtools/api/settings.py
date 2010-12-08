import os

from rbtools.api.utilities import RBUtilities


class Settings(object):
    cwd = os.getcwd()
    cwd = cwd if ('rbtools/rbtools' in cwd) else cwd + '/rbtools'
    CONFIG_FILE = cwd + '/config.dat'

    util = None
    config_file = None
    settings = None

    def __init__(self,util=RBUtilities(),config_file=CONFIG_FILE):
        super(Settings, self).__init__()
        self.util = util
        self.config_file = config_file
        self.settings = {}
        self.load()

    def load(self):
        """loads the settings file"""
        if os.path.isfile(self.config_file):
            file = open(self.config_file, 'r')

            if file < 0:
                util.raise_error('UnknownFileError','Could not open file: ' + config_file)

            self.settings = {}
            line = file.readline()
            while line:
                tuple = line.strip().split()
                self.settings[tuple[0]] = tuple[1]

                line = file.readline()

            file.close()

    def save(self):
        """saves the current settings"""
        keys = self.settings.keys()

        file = open(self.config_file, 'w')

        if file < 0:
            self.util.raise_error('UnknownFileError','Could not open file: ' + config_file)

        for key in keys:
            file.write(key + ' ' + self.settings[key] + '\n')

        file.close()

    def change_setting(self,name,value):
        """changes the value of a setting"""

        if not name in self.settings:
            self.util.raise_warning('UnrecognizedSetting','Setting "' + name + \
                '" does not exist. Adding it in and setting it to "' + value + '"')
            self.add_setting(name,value)
        else:
            self.settings[name] = value
            self.save()

    def add_setting(self,name,value):
        """adds a setting to the settings"""
        if name in self.settings:
            self.util.raise_warning('DuplicateSetting','Setting "' + name + \
                '" already exists. Changing its value to "' + value + '"')
            self.change_setting(name,value)
        else:
            self.settings[name] = value

            file = open( self.config_file, 'a' )

            if file < 0:
                self.util.raise_error('UnknownFileError','Could not open file: ' + config_file)

            file.write(name + ' ' + value + '\n')
            file.close()

    def remove_setting(self,name):
        """removes a setting"""
        if name not in self.settings:
            self.util.raise_warning('UnkownSetting','Setting "' + name + \
                'does not exist')
                
        del self.settings[name]
        self.save()

    def get_setting(self,name):
        """returns a setting"""
        value = None

        if name not in self.settings:
            self.util.raise_warning('UnkownSetting','Setting "' + name + \
                'does not exist')
        else:
            value = self.settings[name]

        return value

    def set_server_url(self,value):
        self.change_setting('server_url',value)

    def set_api_uri(self,value):
        self.change_setting('api_uri',value)

    def set_cookie_file(self,value):
        self.change_setting('cookie_file',value)

    def get_server_url(self):
        return self.get_setting('server_url')

    def get_api_uri(self):
        return self.get_setting('api_uri')

    def get_cookie_file(self):
        return self.get_setting('cookie_file')
