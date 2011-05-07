import os
import re
import sys
import urllib2

from rbtools.api.resource import Resource, \
                                 RootResource, \
                                 ReviewRequest, \
                                 RESOURCE_LIST, \
                                 ROOT
from rbtools.api.serverinterface import ServerInterface
from rbtools.api.settings import Settings
from rbtools.api.errors import ResourceError
from rbtools.commands.utils import json_to_string


UP = 'up()'
TOP = 'top()'
HELP = 'help()'
QUIT = 'quit()'
MORE = 'more()'


class Main(object):
    def __init__(self):
        super(Main, self).__init__()        
        valid = False
        interactive_mode = False
        self.root = None
        self.current = None
        self.stack = []
        self.children = None
        self.children_index = 0
        self.more_valid = False

        if len(sys.argv) > 1:
            settings = Settings(config_file='rb_scripts.dat')
            cookie = settings.get_cookie_file()
            server_url = settings.get_server_url()
            server = ServerInterface(server_url, cookie)
            self.root = RootResource(server, server_url + 'api/')
            self.current = self.root
            self.stack.append(self.root)

            if re.match('-i', sys.argv[1]):
                valid = True
                interactive_mode = True

            if len(sys.argv) > 2:
                if re.match('-r', sys.argv[2]):
                    pass
                #continue along the resource chain that is specified
                #resource_name = re.split('-', sys.argv[1])[1]
                #resource_list = root.get(resource_map[resource_name])

            #if len(sys.argv) > 2 and sys.argv[2]:
                #resource_id = sys.argv[2]
                #resource = resource_list.get(resource_id)
                #print json_to_string(resource.data)
            #else:
                #print json_to_string(resource_list.data)

            print json_to_string(self.current.data)

            if interactive_mode:
                self.print_start()
                command = self.get_command()

                while command != QUIT:
                    self.process_command(command)
                    command = self.get_command()

        if not valid:
            print "usage: rb info [-i] [-r <resource_link_name> [resource_id]] " \
                  ".. [-r <resource_link_name> [resource_id]]"
            print ""
            print "options:"
            print "       -i    Used to specify interactive mode."
            print "       -r    Used to indicate a child resource.  The name of " \
                  "resource link must immediately follow.  Optionally, after " \
                  "the name of the resource link the resource id may be used " \
                  "to get the actual resource, rather than the list. " \
                  "Subsequent sets of '-r <resource_link_name> [resource_id]' " \
                  "may be included to follow down the chain and arrive at a " \
                  "final resource or resource list." 

    def process_command(self, cmd):
        if cmd == HELP:
            self.print_help()
        elif cmd == MORE:
            if self.more_valid:
                self.print_id_list()
            else:
                self.print_bad_command()
        else:
            valid_command = True
            self.more_valid = False

            if cmd == UP:
                self.up()
            elif cmd == TOP:
                self.top()
            else:
                try:
                    current_resource_name = self.current.resource_name

                    if self.current.resource_type == RESOURCE_LIST:
                        self.current = self.current.get(cmd)
                    else:
                        self.current = self.current.get_or_create(cmd)

                    if current_resource_name != self.current.resource_name:
                        self.stack.append(self.current)

                    try:
                        temp_links = self.current.get_links()
                        self.current_links = {}
                        for n in temp_links:
                            if temp_links[n]['method'] == "GET":
                                self.current_links[n] = temp_links.get(n)
                    except KeyError, e:
                        print "DEBUG %s" % e
                        pass
                except ResourceError, e:
                    valid_command = False
                    #print e
                    self.print_bad_command()
                except urllib2.HTTPError, e:
                    print e

            if valid_command:
                print json_to_string(self.current.data)

    def print_bad_command(self):
        print "The command given is invalid at this section.  Please try again."
        print "For more information, type '%s'\n" % HELP

    def get_command(self):
        return raw_input(">")

    def print_help(self):
        print "The interactive commands available from this resource are: "
        print "\tGeneral:"
        print "\t\t%s" % UP
        print "\t\t%s" % TOP
        print "\t\t%s" % QUIT
        print "\t\t%s" % HELP

        if len(self.current_links) > 0:
            print "\tLinks:"

            for n in self.current_links:
                print "\t\t%s" % n

        if self.current.resource_type == RESOURCE_LIST and \
            self.current.resource_name != ROOT:
            self.children = self.current.data[self.current.resource_name]
            self.children_index = 0
            self.print_id_list()
        else:
            print ""

    def print_id_list(self):
        counter = 0
        print "\tIDs (out of %d):" % len(self.children)

        while self.children_index < len(self.children) and counter < 5:
            print "\t#%d\t%s" % \
                (self.children_index + 1, 
                 self.children[self.children_index][
                    self.resource_name_to_id(self.current.resource_name)
                  ]
                )
            counter = counter + 1
            self.children_index = self.children_index + 1

        if self.children_index < len(self.children):
            print "\t..\t(type '%s' to see more)" % MORE    
            self.more_valid = True
        else:
            self.more_valid = False

        print ""

    def resource_name_to_id(self, resource_name):
        if resource_name == 'users':
            return 'username'
        elif resource_name == 'diffs':
            return 'revision'
        else:
            return 'id'

    def print_start(self):
        print "You have now entered the interactive mode.  You may enter one " \
              "of:\n" \
              "     the name of a resource link, or\n" \
              "     a resource id to continue down the resource chain,\n" \
              "     '%s' to go up a level,\n" \
              "     '%s' to return to the root resource,\n" \
              "     '%s' to quit, or finally\n" \
              "     '%s' for more information.\n" % (UP, TOP, QUIT, HELP)

    def up(self):
        if len(self.stack) > 1:
            self.stack.pop()
    
        self.current = self.stack[len(self.stack) - 1]

    def top(self):
        while len(self.stack) > 1:
            self.stack.pop()

        self.current = self.root


def main():
    main = Main()


if __name__ == '__main__':
    main()
