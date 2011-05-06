#!/usr/bin/env python

import gtk
import os
import pygtk
pygtk.require('2.0')
import sys
import urllib2

try:
    from json import loads as json_loads
except ImportError:
    from simplejson import loads as json_loads

from rbtools.api.serverinterface import ServerInterface
from rbtools.api.settings import Settings
from rbtools.api.resource import Resource, ResourceList, RootResource
from rbtools.api.resource import RESOURCE, RESOURCE_LIST


COOKIE_FILE = None
SERVER_URL = None


class ResourceWidget(gtk.ScrolledWindow):
    def __init__(self, hadjustment=None, vadjustment=None, server_url=SERVER_URL, is_root=True):
        super(ResourceWidget, self).__init__()
        self.set_border_width(10)
        self.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_ALWAYS)
        self.main_box = gtk.VBox(False, 10)
        self.main_box.show()
        self.add_with_viewport(self.main_box)
        
        self.server_url = server_url
        self.init_root_resource(is_root)

        self.header_table = gtk.Table(1, 3)
        self.header_table.show()
        self.tree_box = gtk.VBox(False, 0)
        self.tree_box.show()
        tree_label = gtk.Label("Resource Tree:")
        tree_label.show()
        self.tree_box.pack_start(tree_label)
        self.header_table.attach(self.tree_box, 0, 1, 0, 1)
        self.current_tree_size = 0
        self.update_tree()
        self.main_box.pack_start(self.header_table)

        self.actions_box = gtk.VBox(False, 0)
        self.actions_box.show()
        actions_label = gtk.Label("Actions:")
        actions_label.show()
        self.actions_box.pack_start(actions_label)
        self.header_table.attach(self.actions_box, 2, 3, 0, 1)        

        self.table = None
        self.get_id = None
        self.changes = {}
        self.build_table(self.root.data)


    def init_root_resource(self, is_root=True):
        self.server = ServerInterface(self.server_url, COOKIE_FILE)

        if is_root:
            self.root = RootResource(self.server, self.server_url)
        else:
            self.root = Resource(self.server, self.server_url)
            self.root._load()

        self.current = self.root
        self.stack = []
        self.stack.append([self.root, self.make_parent_button(self.root.resource_name)])

        self.actions = []

    def parent_clicked(self, widget, data):
        curr = self.stack[len(self.stack) - 1]

        while not curr[0].resource_name == data:
            curr = self.stack.pop()
            curr[1].hide()
            self.tree_box.remove(curr[1])
            self.current_tree_size = self.current_tree_size - 1        
            curr = self.stack[len(self.stack) - 1]

        self.current = curr[0]
        self.link_clicked(None, 'self')
        #self.build_table(self.current.data)

    def link_clicked(self, widget, data):
        if data:
            if data == 'update':
                try:
                    for n in self.changes.keys():
                        self.current.update_field(n, self.changes[n])

                    self.current.save()
                except urllib2.HTTPError, e:
                    #print e.read()
                    pass
            elif data == 'create':
                error = True
                self.current = self.current.create()
                
                while error:
                    try:
                        self.current.save()
                        error = False
                    except urllib2.HTTPError, e:
                        text = e.read()
                        text_json = json_loads(text)
                        if 'fields' in text_json:
                            for n in text_json['fields']:
                                print 'Missing Field Required!'
                                print 'Please enter a value for %s' % n
                                value = raw_input('%s: ' % n)
                                self.current.update_field(n, value)
                        else:
                            self.current.clear_updates()

                self.stack.append([self.current, self.make_parent_button(self.current.resource_name)])
                self.update_tree()                            
            else:
                if data == 'get_button':
                    data = self.get_id.get_text()

                current_resource_name = self.current.resource_name
    
                if self.current.resource_type == RESOURCE:
                    self.current = self.current.get_or_create(data)
                else:
                    self.current = self.current.get(data)
    
                if not current_resource_name == self.current.resource_name:
                    self.stack.append([self.current, self.make_parent_button(self.current.resource_name)])
                    self.update_tree()

            self.changes = {}
            self.build_table(self.current.data)

    def entry_changed(self, widget, n):
        self.changes[n] = widget.get_text()
        #print "%s changed to %s" % (n, self.changes[n])

    def update_tree(self):
        i = len(self.stack)

        if i > self.current_tree_size:
            i = self.current_tree_size
            
            while i < len(self.stack):
                self.tree_box.pack_start(self.stack[i][1])
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
        self.clear_actions()
        if self.current.resource_type == RESOURCE_LIST:
            get_box = gtk.HBox(False, 0)
            get_box.show()
            self.actions.append(get_box)
            self.actions_box.pack_start(get_box)
            self.get_id = gtk.Entry()
            self.get_id.set_editable(True)
            self.get_id.show()
            get_box.pack_end(self.get_id)
            get_button = gtk.Button('Get: ')
            get_button.connect("clicked", self.link_clicked, 'get_button')
            get_button.show()
            get_box.pack_start(get_button)

        rows, cols = self.get_dimensions(data)
        cols = cols + 1
        
        if self.table:
            self.main_box.remove(self.table)

        #print "rows %d, cols %d" % (rows, cols)
        self.table = gtk.Table(rows, cols)
        self.table.show()
        self.main_box.pack_start(self.table)
        self.populate_table(data, columns=cols)
 
    def populate_table(self, data, k=0, l=0, links=False, columns=1):
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
                        #print "%s at %d, %d, %d, %d" % (n, j, j+1, i, i+1)
                        self.table.attach(next, j, j + 1, i, i + 1)
                        
                    i = i + 1
                    j = j + 1
                    i = self.populate_table(data[n], i, j, lnks, columns) - 1
                    j = j - 1
                else:
                    next_label = gtk.Label("%s: " % n)
                    next_label.set_justify(gtk.JUSTIFY_LEFT)
                    next_label.show()
                    #print "%s at %d, %d, %d, %d" % (n, j, j+1, i, i+1)
                    self.table.attach(next_label, j, j + 1, i, i + 1)
                    j = j + 1

                    if isinstance(data[n], list):
                        if len(data[n]) > 0:
                            scroll_window = gtk.ScrolledWindow()
                            scroll_window.show()
                            scroll_window.set_border_width(5)
                            scroll_window.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_ALWAYS)
                            #print "attaching scroll window at %d, %d, %d, %d" % (j, columns + 1, i, i+1)
                            self.table.attach(scroll_window, j, columns + 1, i, i + 1)
                            vbox = gtk.VBox(False, 0)
                            vbox.show()
                            scroll_window.add_with_viewport(vbox)
                            
                            # if it is a list where item's in the list have 'links',
                            # then its a list of resources
                            if not isinstance(data[n][0], int):
                                if 'links' in data[n][0]:
                                    for x in data[n]:
                                        if 'users' == n:
                                            id_name = 'username'
                                        elif 'diffs' == n:
                                            id_name = 'revision'
                                        else:
                                            id_name = 'id'
   
                                        button_text = '%s: ' % x[id_name] 

                                        if 'review_requests' == n:
                                            button_text = button_text + '\n%s' % x['summary']
                                        elif 'repositories' == n:
                                            button_text = button_text + '\n%s' % x['name']
    
                                        id_button = gtk.Button(button_text)
                                        id_button.connect('clicked', self.link_clicked, x[id_name])
                                        id_button.show()
                                        vbox.pack_start(id_button)
                                    
                            # else its a plain ol' list
                            else:
                                for x in data[n]:
                                    next_box = gtk.Entry()
                                    next_box.set_editable(False)
                                    next_box.set_text(str(x))
                                    vbox.pack_start(next_box)
                        else:
                            next_box = gtk.Entry()
                            next_box.set_editable(False)
                            next_box.set_text(str(data[n]))
                            next_box.show()
                            #print "%s at %d, %d, %d, %d" % (str(data[n]), j, j+1, i, i+1)
                            self.table.attach(next_box, j, j + 1, i, i + 1)
                     
                        j = j - 1
                    else:
                        next_box = gtk.Entry()
                        next_box.set_editable(True)
                        next_box.set_text(str(data[n]))
                        next_box.connect('changed', self.entry_changed, n)
                        next_box.show()
                        #print "%s at %d, %d, %d, %d" % (str(data[n]), j, j+1, i, i+1)
                        self.table.attach(next_box, j, j + 1, i, i + 1)
                        j = j - 1
            #else:
            #    next_button = gtk.Button("%s" % n)
                        
            else:
                next_button = gtk.Button("%s" % n)
                next_button.connect("clicked", self.link_clicked, n)
                next_button.show()
                self.actions.append(next_button)
                self.add_action_button(next_button)
                #self.table.attach(next_button, j, j + 1, i, i + 1)
               
            i = i + 1
           
        return i
    
    def add_action_button(self, button):
        self.actions_box.pack_start(button)

    def clear_actions(self):
        for n in self.actions:
            self.actions_box.remove(n)

        self.actions = []

"""
    def msg_entry_change(self, widget):
        self.prompt_text = widget.get_text()

    def msg_entry_submit(self, widget):
        
        self.prompt_msg_box.destroy()    

    def prompt_for_text(self, field):
        msg_box = gtk.Dialog()
        msg_box.show()
        msg_box.set_size_request(500, 500)
        msg_box.set_title('Missing required field')
        msg_text = gtk.Label('The field "%s" is required.  Please enter the field''s value.' % field)
        msg_text.show()
        msg_box.vbox.pack_start(msg_text)
        msg_entry = gtk.Entry()
        msg_entry.set_editable(True)
        msg_entry.connect('changed', self.msg_entry_changed)
        msg_box.vbox.pack_start(msg_entry)
        msg_submit = gtk.Button('Submit')
        msg_submit.show()
        msg_submit.connect('clicked', self.msg_entry_submit)
        msg_box.vbox.pack_start(msg_submit)
"""   


class ResourceBrowser(object):
    def __init__(self, server_url=SERVER_URL):
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
    settings = Settings(config_file='rb_scripts.dat')
    COOKIE_FILE = settings.get_cookie_file()
    SERVER_URL = settings.get_server_url()
    browser = ResourceBrowser(SERVER_URL)

    gtk.main()

if __name__ == "__main__":
    main()
