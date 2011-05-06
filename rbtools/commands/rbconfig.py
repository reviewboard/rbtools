import os
import string
import sys

from rbtools.api.settings import Settings


SERVER_URL = '--server-url'
COOKIE_FILE = '--cookie-file'
USER_NAME = '--user-name'
CLEAR = '-c'
PRESET_SETTINGS = [
    SERVER_URL,
    COOKIE_FILE,
    USER_NAME,
]


def main():
    valid = False

    if len(sys.argv) > 1:
        valid = True
        cwd = os.getcwd()
        scripts_config = os.path.join(cwd, 'rb_scripts.dat')
        settings = Settings(config_file=scripts_config)
        arg_index = 1

        if sys.argv[arg_index] == CLEAR:
            settings.clear()
            arg_index = arg_index + 1
        
        while arg_index < len(sys.argv):
            split = string.split(sys.argv[arg_index], ':', 1)
            arg_index = arg_index + 1

            if split[0] in PRESET_SETTINGS:
                if split[0] == SERVER_URL:
                    settings.set_server_url(split[1])
                elif split[0] == COOKIE_FILE:
                    settings.set_cookie_file(split[1])
                elif split[0] == USER_NAME:
                    settings.change_setting('user_name', split[1])
                else:
                    # The above case statement needs to be updated
                    pass
            else:
                settings.add_setting(split[0], split[1])

        settings.save()

    if not valid:
        print "usage: rb config [-c] [config_item_name:config_item_setting] " \
              ".. [config_item_name:config_item_setting]"
        print ""
        print "Include -c to clear the settings file."
        print "The preset config_item_names are:"

        for n in PRESET_SETTINGS:
            print "    %s" % n


if __name__ == "__main__":
    main()
