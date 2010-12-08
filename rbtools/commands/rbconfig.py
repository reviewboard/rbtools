import os

from rbtools.api.settings import Settings


def main():
    # For now, just init the default/testing settings
    cwd = os.getcwd()
    scripts_config = os.path.join(cwd, 'rb_scripts.dat')
    settings = Settings(config_file=scripts_config)
    settings.set_server_url('http://demo.reviewboard.org/')
    settings.set_cookie_file('.rb_cookie')
    settings.add_setting('user_name', 'dionyses')
    settings.save()


if __name__ == "__main__":
    main()
