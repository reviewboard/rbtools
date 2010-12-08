import re
import urllib2

import serverinterface
from errors import *

try:
    from json import loads as json_loads
except ImportError:
    from simplejson import loads as json_loads


RESOURCE = 'Resource'
RESOURCE_LIST = 'Resource List'
ROOT_RESOURCE = 'Root Resource'


class ResourceBase(object):
    """ Base class from which other Resource objects should inherit.
    """
    def __init__(self, server_interface):
        super(ResourceBase, self).__init__()
        self.url = None
        self.server_interface = server_interface
        self.resource_name = None
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

    def get_fields(self):
        """ provides a list of fields in the resource

        Returns a list of the keys for the fields that exist in the
        resource with the exception of links, as those are handled
        separately. If need be, the resource name will be filtered
        out first.
        """
        fields = self.data.keys()

        if self.resource_name in self.data:  # go to subdictionary
            #could contain a sublist, not a subdictionary
            sub = self.data[self.resource_name]
            if isinstance(sub, dict):
                fields = sub.keys()
            elif isinstance(sub, list):
                fields = []
                for i in range(len(sub)):
                    fields.append(i + 1)  # rbservers are publicly 1-indexed
            else:
                print 'field data is unparsable:\n' + str(sub)
                exit()

        if ('links' in fields):
            fields.remove('links')

        return fields

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

    def get_file(self, accept='*/*'):
        """returns the file located at the current path

        This makes an HTTP GET request to the server on this resource's url.
        This is almost completetly the same as resource_string (as loaded in
        _load()), except this adds the optional field of accept for defining
        mime_type.
        """
        return self.server_interface.get(self.url, accept)

    def _load(self):
        """ Loads and populates data from the server.

        This makes an HTTP GET request to the server on this resource's url.
        Once complete, the data received is loaded into this resource's data
        dictionary and it is verified that the request was successful.
        """
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

    def query_resource_type(self, resource_url):
        """ Queries the url and returns its resource type

        The specified resource url is queryed and its resource type is
        returned.  Possible resource types are:
            RESOURCE
            RESOURCE_LIST
            ROOT_RESOURCE
        """
        if re.search('(api/)$', resource_url):
            return ROOT_RESOURCE
        else:
            # HTTP GET the resource to find out if it is a resource list
            # or a resource
            resp = self.server_interface.get(resource_url)
            data_list = json_loads(resp)

            if _is_resource_list(data_list):
                return RESOURCE_LIST
            else:
                return RESOURCE


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
        self.resource_type = RESOURCE
        self.updates = {}
        self.file_updates = {}

    def _determine_resource_name(self):
        """ Attempts to determine and set the resource type.
        """
        # If the resource has been loaded
        if self._queryable:
            for elem in self.data:
                # If the element in the root is not 'stat' then it is the
                # resource type
                if elem != 'stat':
                    self.resource_name = elem
        # Otherwise self.data has not be populated
        else:
            raise UnloadedResourceError(
                'The resource has not been loaded yet.  You must save or '
                'load the resource before attempting to pull data from it.')

    def delete(self):
        """ Deletes the current resource
        """
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
        # This is an update, perform a put
        if self._queryable:
            self.resource_string = \
                self.server_interface.put(self.url, self.updates,
                                          self.file_updates)
        else:
            self.resource_string = \
                self.server_interface.post(self.url, self.updates,
                                           self.file_updates)

        self.data = json_loads(self.resource_string)
        self._queryable = True

        if not self.is_ok():
                raise RequestFailedError('The resource requested could not '
                    'be retrieved - The server response was: %s, %s' %
                    (self.data['stat'], self.data['err']))

        self._determine_resource_name()
        # If it is the first time save() is called on this resource then url
        # is set to the parent's create url.  Update this to self so that
        # future calls will go to the right place.
        self.url = self.get_link('self')

    def _load(self):
        """ Loads the resource from the server.
        """
        super(Resource, self)._load()
        self._determine_resource_name()

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
            key_list = [self.resource_name] + key_list
        else:
            key_list = [self.resource_name, key_list]

        return super(Resource, self).get_field(key_list)

    def update_field(self, field, value):
        """ Records an update to be made to the resource.

        Updates the specified field to the specified value.  Changes are not
        PUT/POSTed to the server until "save()" is called.
        """
        self.updates[field] = value

    def update_file(self, path, file_data):
        """ Records a file update to be made to the resource.

        Updates the specified path to the specified file_data.  Changes are
        not PUT/POSTed to the server until "save()" is called.
        """
        self.file_updates[path] = file_data

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
        url = self.get_link(link)

        try:
            # First create the resource if it doesn't already exist by
            # performing a blank post to the url
            resp = self.server_interface.post(url, {})
        except urllib2.HTTPError, e:
            if e.code == 500:
                pass
            elif e.code == 400:
                pass
            elif e.code == 405:
                pass
            else:
                raise e

        target_resource_type = self.query_resource_type(url)

        if target_resource_type == RESOURCE_LIST:
            return ResourceList(self.server_interface, url)
        elif target_resource_type == RESOURCE:
            rsc = Resource(self.server_interface, url)
            # _load it before returning it
            rsc._load()
            return rsc
        else:
            return RootResource(self.server_interface, url)


class ResourceListBase(ResourceBase):
    """ An base object which specifically deals with lists of resources.
    """
    def __init__(self, server_interface, url):
        super(ResourceListBase, self).__init__(server_interface)
        self.url = url
        self.resource_type = RESOURCE_LIST
        # Set the _index for iteration to -1.  Each call to next() will first
        # increment the index then attempt to return the item
        self._index = -1
        self._load()

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
            child_url = self.url + str(field_id) + '/'
            rsc = Resource(self.server_interface, child_url)
            rsc._load()
            return rsc
        else:
            if field_id:
                try:
                    url = self.get_link(field_id)
                except InvalidKeyError, e:
                    # There is no link named field_id, but field_id might
                    # be a child resource whos id isn't numeric
                    try:
                        child_url = self.url + field_id + '/'
                        rsc = Resource(self.server_interface, child_url)
                        rsc._load()
                        return rsc
                    except urllib2.HTTPError, e:
                        raise RequestFailedError(
                            'The resource child could not be retrieved.')

                target_resource_type = self.query_resource_type(url)

                if target_resource_type == RESOURCE_LIST:
                    return ResourceList(self.server_interface, url)
                elif target_resource_type == RESOURCE:
                    rsc = Resource(self.server_interface, url)
                    # _load it before returning it
                    rsc._load()
                    return rsc
                else:
                    return RootResource(self.server_interface, url)
            else:
                raise UnknownResourceNameError(
                    'The resource link could not be retrieved because '
                    'this resource does not contain the link specified.')

    # Methods which allow for the ResourceList to be Iterable.
    def __iter__(self):
        return self

    def next(self):
        return self.__next__()

    def __next__(self):
        self._index += 1

        if self._index == len(self):
            self._index = -1
            raise StopIteration
        else:
            return self.get(self.data[self.resource_name][self._index]['id'])

    # Methods which allow for the ResourceList to behave like a Sequence.
    # That is, they allow the ResourceList to be indexed or sliced.
    def __len__(self):
        return len(self.data[self.resource_name])

    def __contains__(self, key):
        for n in self:
            if n == key:
                return True

        return contains

    def __getitem__(self, position):
        if isinstance(position, slice):
            rscs = []
            resources = self.get_field(self.resource_name)[position]

            for n in resources:
                rsc = Resource(self.server_interface,
                               n['links']['self']['href'])
                rsc._load()
                rscs.append(rsc)
        else:
            rscs = Resource(self.server_interface,
                self.get_field(self.resource_name)[position] \
                ['links']['self']['href'])
            rscs._load()

        return rscs


class ResourceList(ResourceListBase):
    """ Handles resource list type objects.
    """
    def __init__(self, server_interface, url):
        super(ResourceList, self).__init__(server_interface, url)

    def _load(self):
        """ Loads the resource list from the server.
        """
        super(ResourceListBase, self)._load()
        # Determine and set the resource list's resource type
        for elem in self.data:
            if elem not in ['stat', 'links', 'total_results', 'uri_templates']:
                self.resource_name = elem

        if not _is_resource_list(self.data):
            raise InvalidResourceTypeError(
                'The resource loaded as a resource list is not a resource '
                'list.')

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


class RootResource(ResourceListBase):
    """ Resource list specific to the root.
    """
    def __init__(self, server_interface, url):
        super(RootResource, self).__init__(server_interface, url)
        if not re.search('(api/)$', self.url):
            raise InvalidResourceTypeError(
                'The resource loaded as a RootResource is not a root.')

    def _load(self):
        """ Loads the resource list from the server.
        """
        super(ResourceListBase, self)._load()
        self.resource_name = 'root'

    def __next__(self):
        self._index += 1

        if self._index == len(self):
            self._index = -1
            raise StopIteration
        else:
            return self.get(self.get_links().keys()[self._index])

    def __len__(self):
        return len(self.get_links())

    def __getitem__(self, position):
        if isinstance(position, slice):
            rscs = []
            resource_lists = self.get_links().keys()[position]

            for n in resource_lists:
                rscs.append(self.get(n))
        else:
            rscs = self.get(self.get_links().keys()[position])

        return rscs


class ResourceSpecific(Resource):
    """ Base class for specific resource types.

    The base class to make specific resources which are initialized from
    an already constructed resource.
    """
    def __init__(self, resource):
        if isinstance(resource, Resource):
            super(ResourceSpecific, self).__init__(resource.server_interface,
                                           resource.url)
            if resource._queryable:
                self.resource_string = resource.resource_string
                self.data = resource.data
                self._queryable = resource._queryable
                self.resource_name = resource.resource_name
            else:
                self._load()


class ReviewRequestDraft(ResourceSpecific):
    """ Resource specific to a review request draft.
    """
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


class ReviewRequest(ResourceSpecific):
    """ Resource specific to a review request.
    """
    PENDING = 'pending'
    DISCARDED = 'discarded'
    SUBMITTED = 'submitted'

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


class DiffResource(ResourceSpecific):
    """Resource associated with diff files on RB servers"""


class RepositoryList(ResourceList):
    """ Resource list specific to a list of repositories.
    """
    def __init__(self, resource_list):
        if isinstance(resource_list, ResourceList):
            super(RepositoryList, self).__init__(
                resource_list.server_interface, resource_list.url)

    def get_repository_id(self, path):
        """ Finds the repository which matches the path.

        Gets the ID of the repository from the list where the path matches the
        path specified.

        Parameters:
            path    The path of the repository to match.  This should be the
                    upstream path of the repository.

        Returns:
            The ID of the repository from the list which matches the path
            specified.  If no match is found, then None is returned.
        """
        for repo in self:
            if repo.get_field('path') == path:
                return repo.get_field('id')

        return None


# Auxillary methods not specific to any resource
def _is_resource_list(data):
    """ Returns true if the data set is a resource list.

    Returns True if the specified data set includes a field 'total_results'.
    Otherwise, false is returned.
    """
    return 'total_results' in data
