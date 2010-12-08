#!/usr/bin/env python

import gtk
import os
import pygtk
pygtk.require('2.0')
import sys

from rbtools.api.serverinterface import ServerInterface
from rbtools.api.resource import Resource, ResourceList, RootResource
from rbtools.api.resource import RESOURCE


DEFAULT_SERVER_URL = 'http://demo.reviewboard.org/'


class ResourceWidget(gtk.ScrolledWindow):
    def __init__(self, hadjustment=None, vadjustment=None, server_url=DEFAULT_SERVER_URL, is_root=True):
        super(ResourceWidget, self).__init__()
        self.set_border_width(10)
        self.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_ALWAYS)
        self.main_box = gtk.VBox(False, 0)
        self.main_box.show()
        self.add_with_viewport(self.main_box)
        
        self.server_url = server_url
        self.init_root_resource(is_root)

        self.tree_box = gtk.HBox(False, 0)
        self.tree_box.show()
        self.tree = gtk.VBox(False, 0)
        self.tree.show()
        self.tree_box.pack_start(self.tree)
        self.current_tree_size = 0
        self.update_tree()
        self.main_box.pack_start(self.tree_box)

        self.table = None
        self.build_table(self.root.data)

        self.actions = gtk.HBox(False, 0)
        self.actions.show()
        self.main_box.pack_start(self.actions)        

    def init_root_resource(self, is_root=True):
        cwd = os.getcwd()
        cookie = os.path.join(cwd, '.resource_browser_cookie') 
        self.server = ServerInterface(self.server_url, cookie)

        if is_root:
            self.root = RootResource(self.server, self.server_url)
        else:
            self.root = Resource(self.server, self.server_url)
            self.root._load()

        self.current = self.root
        self.stack = []
        self.stack.append([self.root, self.make_parent_button(self.root.resource_name)])

    def parent_clicked(self, widget, data):
        curr = self.stack[len(self.stack) - 1]

        while not curr[0].resource_name == data:
            curr = self.stack.pop()
            curr[1].hide()
            self.tree.remove(curr[1])
            self.current_tree_size = self.current_tree_size - 1        
            curr = self.stack[len(self.stack) - 1]

        self.current = curr[0]
        self.build_table(self.current.data)

    def link_clicked(self, widget, data):
        current_resource_name = self.current.resource_name
        if self.current.resource_type == RESOURCE:
            self.current = self.current.get_or_create(data)
        else:
            self.current = self.current.get(data)
        
        if not current_resource_name == self.current.resource_name:
            self.stack.append([self.current, self.make_parent_button(self.current.resource_name)])
            self.update_tree()

        self.build_table(self.current.data)

    def update_tree(self):
        i = len(self.stack)

        if i > self.current_tree_size:
            i = self.current_tree_size
            
            while i < len(self.stack):
                self.tree.pack_start(self.stack[i][1])
                self.stack[i][1].show()
                i = i + 1

            self.current_tree_size = len(self.stack)

    def make_parent_button(self, name):
        parent_button = gtk.Button(name)
        parent_button.set_size_request(1, 50)
        parent_button.connect('clicked', self.parent_clicked, name)
        return parent_button

    def get_dimensions(self, data, _c=0):
        rows = len(data)
    
        if _c == 0:
            columns = 1
        else:
            columns = _c
       
        max_c = columns
        itr = data.itervalues()
       
        for i in itr:
            if isinstance(i, dict):
                r, c = self.get_dimensions(i, columns + 1)
                rows = rows + r
               
                if c > max_c:
                    max_c = c
       
        columns = max_c
        return rows, columns
      
    def build_table(self, data):
        rows, cols = self.get_dimensions(data)
        cols = cols + 1
        
        if self.table:
            self.main_box.remove(self.table)

        self.table = gtk.Table(rows, cols)
        self.table.show()
        self.main_box.pack_start(self.table)
        self.populate_table(data)
 
    def populate_table(self, data, k=0, l=0, links=False):
        i = k
        j = l
        for n in data:
            if not links:
                if isinstance(data[n], dict):
                    if n == 'links':
                        lnks = True
                    else:
                        lnks = False

                    next = gtk.Label("%s: " % n)
                    next.set_justify(gtk.JUSTIFY_LEFT)
                    next.show()
                    self.table.attach(next, j, j + 1, i, i + 1)
                    i = i + 1
                    j = j + 1
                    i = self.populate_table(data[n], i, j, lnks) - 1
                    j = j - 1
                else:
                    next_label = gtk.Label("%s: " % n)
                    next_label.set_justify(gtk.JUSTIFY_LEFT)
                    next_label.show()
                    self.table.attach(next_label, j, j + 1, i, i + 1)
                    j = j + 1

                    if isinstance(data[n], list):
                        # If there is a first item in data[n] and that item
                        # has a 'links' key, then it is a data[n] is a list
                        # of resources (which should be loaded in their own
                        # ResourceWidgets)
                        if data[n][0] and 'links' in data[n][0]:
                            scroll_window = gtk.ScrolledWindow()
                            scroll_window.show()
                            scroll_window.set_border_width(5)
                            scroll_window.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_ALWAYS)
                            self.table.attach(scroll_window, j, j + 1, i, i + 1)
                            vbox = gtk.VBox(False, 0)
                            vbox.show()
                            scroll_window.add_with_viewport(vbox)

                            for x in data[n]:
                                resource_page = ResourceWidget(None, None, x['links']['self']['href'], False)
                                resource_page.show()
                                vbox.pack_start(resource_page)

                            j = j - 1
                        else:
                            next_box = gtk.Entry()
                            next_box.set_editable(True)
                            next_box.set_text(str(data[n]))
                            next_box.show()
                            self.table.attach(next_box, j, j + 1, i, i + 1)
                            j = j - 1
                    else:
                        next_box = gtk.Entry()
                        next_box.set_editable(True)
                        next_box.set_text(str(data[n]))
                        next_box.show()
                        self.table.attach(next_box, j, j + 1, i, i + 1)
                        j = j - 1
            #else:
            #    next_button = gtk.Button("%s" % n)
                        
            else:
                next_button = gtk.Button("%s" % n)
                next_button.connect("clicked", self.link_clicked, n)
                next_button.show()
                self.table.attach(next_button, j, j + 1, i, i + 1)
               
            i = i + 1
           
        return i
       
class ResourceBrowser(object):
    def __init__(self, server_url=DEFAULT_SERVER_URL):
        super(ResourceBrowser, self).__init__()
        self.window = gtk.Dialog()
        self.window.show()
        self.window.set_size_request(800, 600)
        self.window.set_border_width(0)
        self.server_url = server_url
        self.window.set_title("Resource Browser @ %s" % self.server_url)
        self.resource_page = ResourceWidget(None, None, self.server_url + 'api/')
        self.resource_page.show()
        self.window.vbox.pack_start(self.resource_page)
        self.window.connect('destroy', self.close_application)

    # another callback
    def close_application(self, widget):
        gtk.main_quit()


def main():
    if len(sys.argv) > 1:
        browser = ResourceBrowser(sys.argv[1])
    else:
        browser = ResourceBrowser(DEFAULT_SERVER_URL)

    gtk.main()

if __name__ == "__main__":
    main()
