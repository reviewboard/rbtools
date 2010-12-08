import urllib2

import serverinterface
from errors import *

try:
    from json import loads as json_loads
except ImportError:
    from simplejson import loads as json_loads


class ResourceBase(object):
    """ Base class from which other Resource objects should inherit.
    """
    def __init__(self, server_interface):
        super(ResourceBase, self).__init__()
        self.url = None
        self.server_interface = server_interface
        self.resource_type = None
        self.resource_string = None
        self.data = {}
        self._queryable = False

    def __str__(self):
        if self.resource_string:
            return self.resource_string
        else:
            return "Unloaded Resource."

    def is_ok(self):
        """ Returns true if the resource was retrieved successfully.

        Returns true if the resource was retrieved from the server without
        error.  If the request to the server wasn't successfull for any
        reason, false is returned.
        """
        if not self._queryable:
            raise UnloadedResourceError(
                'The resource has not been loaded yet.  You must save or '
                'load the resource before attempting to pull data from it.')
        else:
            return self.data['stat'] == 'ok'

    def get_field(self, key_list):
        """ Returns the field in the resource mapped by a list of keys.

        Attempts to retrieve the value mapped by the key_list.  As the data
        of a resource may contain dictionaries within dictionaries, each item
        in the key_list is the ordered sequence of keys to retrieve from the
        set of embedded dictionaries.

        If this resource's data is this set of nested dictionaries:

        {'a': {'1': 'one', '2': {'s': 'ess', 't': 'tee'}}, 'b': 'bee'}

        Then the following calls will return each respective value:
        Call                            Field Returned
        get_field(['b'])                'bee'
        get_field(['a', '1'])           'one'
        get_field(['a', '2', 't'])      'tee'
        get_field(['a', '1', 'n'])      InvalidKeyError raised
        get_field(['a', '2', 'x'])      InvalidKeyError raised

        If there is no value found under the specified key_list an INVALID_KEY
        error is raised.

        .. note::
            This should be overwritten in child classes which only want to be
            able to retrieve fields relevant to the specific resource type.

        Parameters:
            key_list - the key(s) which map to a value to be obtained.
                       key_list can be a single (non-list) key, or any list
                       of keys to a set of nested dicts, in order of retrieval.

        Returns:
            The field mapped to by the key_list.
        """
        if not self._queryable:
            raise UnloadedResourceError(
                'The resource has not been loaded yet.  You must save or '
                'load the resource before attempting to pull data from it.')
        else:
            field = None

            if isinstance(key_list, list):
                # Step into the next element/dict indexed by key_list[0]
                # in data.
                field = self.data.get(key_list[0])

                if field:
                    for key in key_list[1:]:
                        if isinstance(field, dict):
                            # Step into the next dict indexed by key_list[n]
                            # in field.
                            field = field.get(key)

                            if field is None:
                                break
                        else:
                            field = None
            else:
                field = self.data.get(key_list)

            if field is None:
                raise InvalidKeyError(
                    '%s is not a valid key for this resource.' % key_list)
            else:
                return field

    def get_links(self):
        """ Returns the links available to this resource.

        This is equivilant to calling get_field('links').
        """
        return self.get_field('links')

    def get_link(self, link_name):
        try:
            link_list = self.get_links()
            return link_list[link_name]['href']
        except KeyError, e:
            raise InvalidKeyError(
                'The resource could not retrieve the link %s.' % link_name)

    def _load(self):
        """ Loads and populates data from the server.

        This makes an HTTP GET request to the server on this resource's url.
        Once complete, the data received is loaded into this resource's data
        dictionary and it is verified that the request was successful.
        """
        if not self.server_interface.is_logged_in():
            raise LoginRequiredError(
                'The server interface must be logged in.')

        self.resource_string = self.server_interface.get(self.url)
        self.data = json_loads(self.resource_string)
        self._queryable = True

        if not self.is_ok():
            raise RequestFailedError(
                'The resource requested could not be retrieved.')

    def refresh(self):
        """ Refreshes the resource from the server.
        """
        self._load()


class Resource(ResourceBase):
    """ An object which specifically deals with resources.

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
    def __init__(self, server_interface, url):
        super(Resource, self).__init__(server_interface)
        self.url = url
        self.updates = {}

    def _determine_resource_type(self):
        """ Attempts to determine and set the resource type.
        """
        # If the resource has been loaded
        if self._queryable:
            for elem in self.data:
                # If the element in the root is not 'stat' then it is the
                # resource type
                if elem != 'stat':
                    self.resource_type = elem
        # Otherwise self.data has not be populated
        else:
            raise UnloadedResourceError(
                'The resource has not been loaded yet.  You must save or '
                'load the resource before attempting to pull data from it.')

    def delete(self):
        """ Deletes the current resource
        """
        if not self.server_interface.is_logged_in():
            raise LoginRequiredError(
                'The server interface must be logged in.')

        if self._queryable:
            self.resource_string = self.server_interface.delete(
                self.get_link('delete'))
            self.data = json_loads(self.resource_string)
            self._queryable = False

            if not self.is_ok():
                raise RequestFailedError('The resource requested could not '
                    'be retrieved - The server response was: %s, %s' %
                    (self.data['stat'], self.data['err']))

    def save(self):
        """ Saves the current updates to the resource.
        """
        if not self.server_interface.is_logged_in():
            raise ResourceError(ResourceError.LOGIN_REQUIRED, 'The server '
                'interface must be logged in.')

        self.resource_string = self.server_interface.put(self.url,
                                                         self.updates)
        self.data = json_loads(self.resource_string)
        self._queryable = True

        if not self.is_ok():
                raise RequestFailedError('The resource requested could not '
                    'be retrieved - The server response was: %s, %s' %
                    (self.data['stat'], self.data['err']))

        self._determine_resource_type()
        # If it is the first time save() is called on this resource then url
        # is set to the parent's create url.  Update this to self so that
        # future calls will go to the right place.
        self.url = self.get_link('self')

    def _load(self):
        """ Loads the resource from the server.
        """
        super(Resource, self)._load()
        self._determine_resource_type()

    def get_field(self, key_list):
        """ Retrieves the field mapped to by key_list of this resource.

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
        # Return the parent class' get_field() method but first pre-append
        # this resource's type to the key_list to get the fields specific to
        # this resource
        if isinstance(key_list, list):
            key_list = [self.resource_type] + key_list
        else:
            key_list = [self.resource_type, key_list]

        return super(Resource, self).get_field(key_list)

    def update_field(self, field, value):
        """ Records an update to be made to the resource.

        Updates the specified field to the specified value.  Changes are not
        POSTed to the server until "save()" is called.
        """
        self.updates[field] = value

    def get_or_create(self, link):
        """ Get or create then get the resource specified by link.

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
            # First create the resource if it doesn't already exist by
            # performing a blank put to the url
            resp = self.server_interface.post(self.get_link(link), {})
        except urllib2.HTTPError, e:
            if e.code == 500:
                pass
            else:
                raise e

        # Now GET the resource to find out if it is a resource list
        # or a resource
        resp = self.server_interface.get(self.get_link(link))
        data_list = json_loads(resp)

        # If we are get_or_creating a ResourceList
        if _is_resource_list(data_list):
            return ResourceList(self.server_interface, self.get_link(link))
        # If we are get_or_creating a Resource
        else:
            # Then _load it before returning it
            rsc = Resource(self.server_interface, self.get_link(link))
            rsc._load()
            return rsc


class ResourceList(ResourceBase):
    """
    An object which specifically deals with lists of resources.
    """
    def __init__(self, server_interface, url):
        super(ResourceList, self).__init__(server_interface)
        self.url = url
        self.child_resource_url = None
        self.field_id = None
        # Set the _index for iteration to -1.  Each call to next() will first
        # increment the index then attempt to return the item
        self._index = -1
        self._is_root = False
        self._load()

    def _load(self):
        """ Loads the resource list from the server.
        """
        super(ResourceList, self)._load()

        # Determine and set the resource list's resource type
        for elem in self.data:
            if elem not in ['stat', 'links', 'total_results', 'uri_templates']:
                self.resource_type = elem

        if self.resource_type is None:
            self._is_root = True
        else:
            if not _is_resource_list(self.data):
                raise InvalidResourceTypeError(
                   'The resource loaded as a resource list is not a resource '
                   'list.')
            self._determine_child_url()

    def _determine_child_url(self):
        """ Determine and set the child resource url.
        """
        if self._is_root:
            # There is no such thing as a child resource
            pass
        else:
            # The child resource url comes from appending an id to the
            # end of the resource list's url
            self.child_resource_url = self.url + '{id_field}/'

    def create(self):
        """ Creates a new instance of the resource list's child resource.

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
        except InvalidKeyError, e:
            # there is no 'create' link for this resource
            raise ChildResourceUncreatableError(
                'The request cannot be made because this resource list\'s'
                'child is not creatable.')

        return Resource(self.server_interface, self.get_link('create'))

    def get(self, field_id):
        """ Gets the resource specified relative to this resource list.

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
        if str(field_id).isdigit():
            child_url = self.url + field_id + '/'
            rsc = Resource(self.server_interface, child_url)
            rsc._load()
            return rsc
        #Else the field id specifies a 'link'
        else:
            if field_id:
                try:
                    return ResourceList(self.server_interface,
                                        self.get_link(field_id))
                except InvalidKeyError, e:
                    raise UnknownResourceTypeError(
                        'The resource link could not be retrieved because '
                        'this resource does not contain the link specified.')
            else:
                raise UnknownResourceTypeError(
                    'The resource link could not be retrieved because '
                    'this resource does not contain the link specified.')

    # Methods which allow for the ResourceList to be Iterable.
    def __iter__(self):
        return self

    def __next__(self):
        self._index += 1

        if self._index == len(self):
            self._index = -1
            raise StopIteration
        elif self._is_root:
            return self.get(self.get_links().keys()[self._index])
        else:
            return self.get(self.data[self.resource_type][self._index]['id'])

    # Methods which allow for the ResourceList to behave like a Sequence.
    # That is, they allow the ResourceList to be indexed or sliced.
    def __len__(self):
        if self._is_root:
            return len(self.get_links())
        else:
            return len(self.data[self.resource_type])

    def __contains__(self, key):
        for n in self:
            if n == key:
                return True

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


class ReviewRequestDraft(Resource):
    """ Resource specific to a review request draft.
    """
    def __init__(self, resource):
        if isinstance(resource, Resource):
            super(ReviewRequestDraft, self).__init__(resource.server_interface,
                                           resource.url)
            self._load()

    def publish(self):
        """ Publishes the review request draft.
        """
        self.update_field('public', '1')
        
        try:
            self.save()
        except urllib2.HTTPError, e:
            # If an HTTP 303 error is raised this is a web redirect
            if e.code == 303:
                # This means the publish worked, so do nothing
                pass
            else:
                #Re-raise
                raise e


class ReviewRequest(Resource):
    """ Resource specific to a review request.
    """
    PENDING = 'pending'
    DISCARDED = 'discarded'
    SUBMITTED = 'submitted'

    def __init__(self, resource):
        if isinstance(resource, Resource):
            super(ReviewRequest, self).__init__(resource.server_interface,
                                           resource.url)
            self._load()

    def publish(self):
        """ Publishes the review request.

        Publishes the review request by getting the draft, setting its public
        field to 1 (true), and saving the draft.
        """
        resource = self.get_or_create('draft')
        draft = ReviewRequestDraft(resource)
        draft.publish()
        self.refresh()

    def reopen(self):
        """ Reopens the review request for review.

        Reopens the resource by setting its status field to 'pending' and
        saving it.
        """
        self.update_field('status', self.PENDING)
        self.save()

    def discard(self):
        """ Closes the resource as discarded.

        Closes the resource by setting its status field to DISCARDED and
        saving it.
        """
        self.update_field('status', self.DISCARDED)
        self.save()

    def submit(self):
        """ Closes the resource as submitted.

        Closes the resource by setting its status field to SUBMITTED and
        saving it.
        """
        self.update_field('status', self.SUBMITTED)
        self.save()


# Auxillary methods not specific to any resource
def _is_resource_list(data):
    """ Returns true if the data set is a resource list.

    Returns True if the specified data set includes a field 'total_results'.
    Otherwise, false is returned.
    """
    return 'total_results' in data
