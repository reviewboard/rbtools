import serverinterface
import urllib2

try:
    from json import loads as json_loads
except ImportError:
    from simplejson import loads as json_loads


class ResourceError(Exception):
    IMPROPER_RESOURCE_TYPE = 1
    INVALID_KEY = 2
    INVALID_CHILD_RESOURCE_URL = 3
    LOGIN_REQUIRED = 4
    UNCREATEABLE_CHILD_RESOURCE = 5
    UNKNOWN_RESOURCE_TYPE = 6
    UNLOADED_RESOURCE = 7

    def __init__(self, code, msg, *args, **kwargs):
        Exception(self, *args, **kwargs)
        self.code = code
        self.msg = msg

    def __str__(self):
        code_str = "Resource Error %d: " % self.code
        code_str += self.msg
        return code_str


class ResourceBase(object):
    """
    Base class from which other Resource objects should inherit.
    """
    def __init__(self, server_interface, url_field_ids=None):
        self.url = None
        self.server_interface = server_interface
        self.resource_type = None
        self.resource_string = None
        self.data = {}
        self._queryable = False
        self.url_field_ids = url_field_ids

    def __str__(self):
        if self.resource_string:
            return self.resource_string
        else:
            return "Unloaded ResourceBase Object.. Please load before using."

    def is_ok(self):
        """
        Returns true if the resource was provided from the server without
        error.  If the request to the server wasn't successfull for any
        reason, false is returned.
        """
        if not self._queryable:
            raise ResourceError(ResourceError.UNLOADED_RESOURCE, 'The resource'
                ' has not been loaded yet.  You must save() or _load() the '
                'resource before attempting to pull data from it.')
        else:
            return self.data['stat'] == 'ok'

    def get_field(self, key_list):
        """
        Attempts to retrieve the field mapped by the key_list.
        If there is no value found under the specified key_list an INVALID_KEY
        error is raised.

        .. note::
            This should be overwritten in child classes which only want to be
            able to retrieve fields relevant to the resource.

        Parameters:
            key_list - the key(s) which map to a value to be obtained.
                       key_list can be a single (non-list) key, or any list
                       of keys to a set of nested dicts, in order of retrieval.

        Returns:
            The field mapped to by the key_list.
        """
        if not self._queryable:
            raise ResourceError(ResourceError.UNLOADED_RESOURCE, 'The resource'
                ' has not been loaded yet.  You must save() or _load() the '
                'resource before attempting to pull data from it.')
        else:
            if isinstance(key_list, list):
                field = self.data.get(key_list[0])
                if field:
                    for key in key_list[1:]:
                        field = field.get(key)

                        if field == None:
                            break
            else:
                field = self.data.get(key_list)

            if field == None:
                raise ResourceError(ResourceError.INVALID_KEY, '%s is not a '
                    'valid key for this resource.' % key_list)
            else:
                return field

    def get_links(self):
        """
        Returns the links available to this resource.  This is equivilant to
        calling get_field('links').
        """
        return self.get_field('links')

    def get_link(self, link_name):
        try:
            link_list = self.get_links()
            return link_list[link_name]['href']
        except KeyError, e:
            raise ResourceError(ResourceError.INVALID_KEY, 'The resource could'
                ' not retrieve the link %s' % link_name)

    def _load(self):
        if not self.server_interface.is_logged_in():
            raise ResourceError(ResourceError.LOGIN_REQUIRED, 'The server '
                'interface must be logged in.')

        try:
            self.resource_string = self.server_interface.get(self.url)
            self.data = json_loads(self.resource_string)
            self._queryable = True
        except serverinterface.APIError, e:
            print e
        except urllib2.HTTPError, e:
            print e

        if not self.is_ok():
            raise ResourceError(ResourceError.REQUEST_FAILED, 'The resource '
                'requested could not be retrieved.')

    def refresh(self):
        """
        Refreshes the resource from the server.
        """
        self._load()


class Resource(ResourceBase):
    """
    An object which specifically deals with resources.

    .. notes::
        Resources are not loaded from the server upon instantiation.  This is
        because resources are either "got" or "created" from their parent.  The
        way a resource is loaded is dependant on this.

        If a resource is "created" it is not POSTed to the server until save()
        is called.

        If on the other hand the resource is "got" then it already exists on
        the server.  In this case, after being instantiated _load() should be
        called on the resource to perform a GET to the server.
    """
    def __init__(self, server_interface, url, url_field_ids=None):
        ResourceBase.__init__(self, server_interface, url_field_ids)
        self.url = url
        self.updates = {}

    def _determine_resource_type(self):
        """
        Attempts to determine and set the resource type.
        """
        #If the resource has been loaded
        if self._queryable:
            for elem in self.data:
                #If the element in the root is not 'stat' then it is the
                #resource type
                if elem not in ['stat']:
                    self.resource_type = elem
        #Otherwise self.data has not be populated
        else:
            raise ResourceError(ResourceError.UNLOADED_RESOURCE, 'The resource'
                ' has not been loaded yet.  You must save() or _load() the '
                'resource before attempting to pull data from it.')

    def delete(self):
        """
        Deletes the current resource
        """
        if not self.server_interface.is_logged_in():
            raise ResourceError(ResourceError.LOGIN_REQUIRED, 'The server '
                'interface must be logged in.')

        if self._queryable:
            try:
                self.resource_string = self.server_interface.delete(
                    self.get_link('delete'))
                self.data = json_loads(self.resource_string)
                self._queryable = False
            except serverinterface.APIError, e:
                print e
            except urllib2.HTTPError, e:
                print e

            if not self.is_ok():
                raise ResourceError(ResourceError.REQUEST_FAILED, 'The '
                    'resource requested could not be retrieved - from save.'
                    '  The server response was: %s, %s' % (self.data['stat'],
                    self.data['err']))

    def save(self):
        """
        Saves the current updates to the resource.
        """
        if not self.server_interface.is_logged_in():
            raise ResourceError(ResourceError.LOGIN_REQUIRED, 'The server '
                'interface must be logged in.')

        already_loaded = self._queryable

        #.. note:  removed try/except so that callers may deal with exceptions 
        #try:
        self.resource_string = self.server_interface.put(self.url,
                                                         self.updates)
        self.data = json_loads(self.resource_string)
        self._queryable = True
        #except serverinterface.APIError, e:
            #print e
        #except urllib2.HTTPError, e:
            #print e

        if not self.is_ok():
            raise ResourceError(ResourceError.REQUEST_FAILED, 'The resource '
                'requested could not be retrieved - from save.  The server '
                'response was: %s, %s' % (self.data['stat'], self.data['err']))

        self._determine_resource_type()
        #If it is the first time save() is called on this resource then url
        #is set to the parent's create url.  Update this to self so that future
        #calls will go to the right place.
        self.url = self.get_link('self')

        if not already_loaded:
            if self.url_field_ids:
                self.url_field_ids = self.url_field_ids + [self.get_field('id')]
            else:
                self.url_field_ids = [self.get_field('id')]

    def _load(self):
        """
        Loades the resource from the server.
        """
        super(Resource, self)._load()
        self._determine_resource_type()

    def get_field(self, key_list):
        """
        Attempts to retrieve the field relevant to the resource object mapped
        by the key_list.  If there is no value found under the specified
        key_list an INVALID_KEY error is raised.

        Parameters:
            key_list - the key(s) which map to a value to be obtained.
                       key_list can be a single (non-list) key, or any list
                       of keys to a set of nested dicts, in order of retrieval.

        Returns:
            The field mapped to by the key_list.
        """
        #Return the parent class' get_field() method but pre-append this
        #resource's type to the key_list to get the fields specific to
        #this resource
        if isinstance(key_list, list):
            return super(Resource, self).get_field([self.resource_type] +
                                                   key_list)
        else:
            return super(Resource, self).get_field([self.resource_type,
                                                   key_list])

    def update_field(self, field, value):
        """
        Updates the specified field to the specified value.  Changes are not
        POSTed to the server until "save()" is called.
        """
        self.updates[field] = value

    def get_or_create(self, link):
        """
        Gets the resource specified by link.  If the resource does not yet
        exist on the server then it is first created.

        Parameters:
            link - the link indicating which resource to get.  link must be
                   one of the values from self.get_links()

        Returns:
            The resource specified by link.  This could be either a Resource or
            a ResourceList.

        .. note::
            The resource returned is always already loaded.
        """
        try:
            #First create the resource if it doesn't already exist by
            #performing a blank put to the url
            resp = self.server_interface.post(self.get_link(link), {})
        except urllib2.HTTPError, e:
            if e.code == 500:
                pass
            else:
                print e
        except serverinterface.APIError, e:
            print e

        try:
            #Now GET the resource to find out if it is a resource list
            #or a resource
            resp = self.server_interface.get(self.get_link(link))
            data_list = json_loads(resp)

            #If we are get_or_creating a ResourceList
            if is_resource_list(data_list):
                return ResourceList(self.server_interface,
                                    self.get_link(link), self.url_field_ids)
            #If we are get_or_creating a Resource
            else:
                #Then _load it before returning it
                rsc = Resource(self.server_interface, self.get_link(link),
                               self.url_field_ids)
                rsc._load()
                return rsc
        except serverinterface.APIError, e:
            print e
        except urllib2.HTTPError, e:
            print e


class ReviewRequestDraft(Resource):
    """
    """
    def __init__(self, resource):
        if isinstance(resource, Resource):
            Resource.__init__(self, resource.server_interface, resource.url,
                              resource.url_field_ids)
            self._load()

    def publish(self):
        """
        Publishes the resource by getting the draft, setting the drafts public
        field to 1 (true), and saving the draft.
        """
        self.update_field('public', '1')
        try:
            self.save()
        except urllib2.HTTPError, e:
            #If an HTTP 303 error is raised this is a web redirect
            if e.code == 303:
                #This means the publish worked, so do nothing
                pass
            else:
                #Re-raise
                raise e

class ReviewRequest(Resource):
    """
    """
    def __init__(self, resource):
        if isinstance(resource, Resource):
            Resource.__init__(self, resource.server_interface, resource.url,
                              resource.url_field_ids)
            self._load()

    def publish(self):
        """
        Publishes the resource by getting the draft, setting the drafts public
        field to 1 (true), and saving the draft.
        """
        #Get the draft
        resource = self.get_or_create('draft')
        #Load the draft as a ReviewRequestDraft
        draft = ReviewRequestDraft(resource)
        #Publish the draft
        draft.publish()
        self.refresh()

    def open(self):
        """
        Opens the resource by setting its status field to 'pending' and
        saving it.
        """
        self.update_field('status', 'pending')
        self.save()

    def close(self):
        """
        Closes the resource by setting its status field to "submitted' and
        saving it.
        """
        self.update_field('status', 'submitted')
        self.save()


class ResourceList(ResourceBase):
    """
    An object which specifically deals with lists of resources.
    """
    def __init__(self, server_interface, url, url_field_ids=None):
        ResourceBase.__init__(self, server_interface, url_field_ids)
        self.url = url
        self.child_resource_url = None
        self.field_id = None
        #Set the _index for iteration to -1.  Each call to next() will first
        #increment the index then attempt to return the item
        self._index = -1
        self._is_root = False
        #_load() the resource list from the server
        self._load()

    def _load(self):
        """
        Loades the resource list from the server.
        """
        super(ResourceList, self)._load()
        #Determine and set the resource list's resource type
        for elem in self.data:
            if elem not in ['stat', 'links', 'total_results', 'uri_templates']:
                self.resource_type = elem

        #If the resource list's resource type is None
        if self.resource_type is None:
            #Then it is the root
            self._is_root = True
        #Otherwise it is not a root
        else:
            #Validate that the resource loaded is a resource list
            if not is_resource_list(self.data):
                raise ResourceError(ResourceError.IMPROPER_RESOURCE_TYPE,
                    'The resource loaded as a resource list is not a resource'
                    ' list.')
            #Determine and set the child url template for the resource list
            self._determine_child_url()

    def _determine_child_url(self):
        """
        Determine and set the child resource url.
        """
        try:
            #If this is the root resource list
            if self._is_root:
                #There is no such thing as a child resource
                pass
            #Otherwise it is a normal list
            else:
                #The child resource url comes from the 'uri_templates'
                self.child_resource_url = self.get_field(['uri_templates',
                                                     self.resource_type,
                                                     'href'])
        except ResourceError, e:
            print e
            print "MOST LIKELY, THIS ERROR HAS OCCURRED BECAUSE THE REVIEW"
            "BOARD SERVER DOES NOT CURRENTLY STORE 'uri_templates' FOR EACH"
            " RESOURCE LIST"
            print "Guessing child resource url is: "
            self.child_resource_url = self.url
            self.child_resource_url += '{some_id_field}/'
            if self.url_field_ids:
                reverse_url_field_ids = self.url_field_ids
                reverse_url_field_ids.reverse()
                for n in reverse_url_field_ids:
                    temp = self.child_resource_url.rpartition(str(n))
                    if temp[0] is None:
                        print "Error guessing.."
                    else:
                        self.child_resource_url = temp[0] + \
                            '{some_id_field}' + temp[2]

            print self.child_resource_url

    def create(self):
        """
        Attempts to create a new instance of the resource list's child resource
        type.  If the resource list does not define a 'create' link then a
        CHILD_RESOURCE_UNCREATABLE ResourceError is raised.

        Returns:
            The instantiated but unloaded child Resource.

        .. note::
            The resource returned is never already loaded.  To load it, call
            "save()"
        """
        try:
            self.get_link('create')
        except resource.ResourceError, e:
            if e.code == ResourceError.INVALID_KEY:
                #there is no 'create' link for this resource
                raise ResourceError(ResourceError.CHILD_RESOURCE_UNCREATABLE,
                    'The request cannot be made because this resource list\'s'
                    'child is not creatable.')
            else:
                print e

        return Resource(self.server_interface, self.get_link('create'),
                        self.url_field_ids)

    def get(self, field_id):
        """
        Gets and returns the child resource specified by field_id.  The type
        of resource returned is dependant on the field_id specified.

        Parameters:
            field_id - the field id with which to get the child resource.  If
                       the resource being retrieved is a resource list then
                       field_id must be one of the items in self.get_links().
                       Otherwise, the field_id should be the database 'id' of
                       the child resource to retrieve.

        Returns:
            The child resource specified by field_id, which could be either a
            ResourceList or a Resource.

        .. note::
            The resource returned is always already loaded.
        """
        #If the field id specifies an id
        if str(field_id).isdigit():
            #Get the resource by creating the child resource url filled in with
            #the specified field_id
            if self.url_field_ids:
                url = build_resource_url(self.child_resource_url,
                                         self.url_field_ids + [field_id])
                rsc = Resource(self.server_interface, url,
                               self.url_field_ids + [field_id])
            else:
                url = build_resource_url(self.child_resource_url,
                                         [field_id])
                rsc = Resource(self.server_interface, url, [field_id])

            rsc._load()
            return rsc
        #Else the field id specifies a link
        else:
            #Get the resource link specified by field_id
            if field_id:
                try:
                    return ResourceList(self.server_interface,
                                        self.get_link(field_id))
                except ResourceError, e:
                    if e.code == ResourceError.INVALID_KEY:
                        raise ResourceError(
                            ResourceError.UNKNOWN_RESOURCE_TYPE,
                            'The resource link could not be retrieved '
                            'because this resource does not contain the '
                            'link specified.')
                    else:
                        raise e
            else:
                raise ResourceError(ResourceError.UNKNOWN_RESOURCE_TYPE,
                            'The resource link could not be retrieved '
                            'because this resource does not contain the '
                            'link specified.')

    """
    Methods which allow for the ResourceList to be Iterable.
    """
    def __iter__(self):
        return self

    def next(self):
        return self.__next__()

    def __next__(self):
        self._index += 1
        if self._index == self.__len__():
            self._index = -1
            raise StopIteration
        else:
            if self._is_root:
                return self.get(self.get_links().keys()[self._index])
            else:
                return self.get(
                    self.data[self.resource_type][self._index]['id'])

    """
    Methods which allow for the ResourceList to behave like a Sequence.  That
    is they allow the ResourceList to be indexed or sliced.
    """
    def __len__(self):
        if self._is_root:
            return len(self.get_links())
        else:
            return len(self.data[self.resource_type])

    def __contains__(self, key):
        contains = False

        for n in self:
            if n == key:
                contains = True
                break

        return contains

    def __getitem__(self, position):
        if isinstance(position, slice):
            rscs = []

            if self._is_root:
                resource_lists = self.get_links().keys()[position]

                for n in resource_lists:
                    rscs.append(self.get(n))

            else:
                resources = self.get_field(self.resource_type)[position]

                for n in resources:
                    rscs.append(self.get(n['id']))
        else:
            rscs = None

            if self._is_root:
                rscs = self.get(self.get_links().keys()[position])
            else:
                rscs = self.get(
                    self.get_field(self.resource_type)[position]['id'])

        return rscs


"""
Auxillary methods not specific to any resource
"""


def build_resource_url(url, url_field_ids):
    out = ''
    field_id_index = len(url_field_ids) - 1
    #Parse out the rightmost set of '{...}'
    split_url = r_section_split(url, '{', '}')

    if split_url is None:
        raise ResourceError(ResourceError.INVALID_CHILD_RESOURCE_URL,
            "couldn't parse the {id} section from the child resource "
            "url")
    else:
        while not split_url is None:
            out = split_url[0]
            out = out + str(url_field_ids[field_id_index])
            out = out + split_url[2]
            split_url = r_section_split(out, '{', '}')
            field_id_index = field_id_index - 1

    return out


def r_section_split(string, left_marker, right_marker):
    """
    Attempts to return the left, center, and right sides of the specified
    string where the first instance of the substring encased in left_maker
    and right_marker from the right side of the string is split as the
    center section.

    Parameters:
        string       - the string to preform the r_section_split on
        left_marker  - the delimiter which indicates the left side of the
                       section to be split
        right_marker - the delimiter which indicates the right side of the
                       section to be split

    Returns:
        An array of three strings, where the 0th item is the left side of the
        specified string, the 1th item is the center section (including the
        left and right markers,) and the 2th item is the right side of the
        specified string.

        If either the left or right markers cannot be found, or the section
        they define is not "left-to-right" and "perfectly bounded", then
        None is returned.

        left-to-right: a set of left and right markers (delimiters) is said to
                       be left-to-right if the position of the start of the
                       left marker is strictly less than the position of the
                       start of the right marker.

        perfectly bounded: a set of left and right markers (delimiters) is said
                           to be perfectly bounded if they are left-to-right
                           and if the left marker does not surpass the right.
                           In other words, if the position of the left marker
                           plus its length is greater than the position of the
                           right marker plus its length, then they are not
                           perfectly bounded.  Otherwise, they are.
    """
    left_pos = string.rfind(left_marker)
    right_pos = string.rfind(right_marker)

    #if the left or right marker cannot be found
    if left_pos == -1 or right_pos == -1:
        return None
    #if the markers are found but positioned incorrectly (not left-to-right)
    elif left_pos > right_pos:
        return None
    #if the left marker extends past the right marker (not perfectly bounded)
    elif left_pos + len(left_marker) > right_pos + len(right_marker):
        return None

    out = [
        string[0:left_pos],
        string[left_pos:right_pos + len(right_marker)],
        string[right_pos + len(right_marker):]
    ]
    return out


def is_resource_list(data):
    """
    Returns True if the specified data set includes a field 'total_results'.
    Otherwise, false is returned.
    """
    for n in data:
        if n == 'total_results':
            return True

    return False
