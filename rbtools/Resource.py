import ServerInterface
try:
    from json import loads as json_loads
except ImportError:
    from simplejson import loads as json_loads


class ResourceError(Exception):
    INVALID_KEY = 1

    def __init__(self, code, msg, *args, **kwargs):
        Exception(self, *args, **kwargs)
        self.code = code
        self.msg = msg

    def __str__(self):
        code_str = "Resource Error %d: " % self.code
        code_str += self.msg
        return code_str

class Resource(object):
    """
    Class used to represent a resource 
    """
    def __init__(self, resource, is_json=True):
        self.url = None
        self.resource = resource
        self.is_json = is_json
        self.data = {}

        if is_json:
            self.data = json_loads(self.resource)
        else:
            #Preform deserialization for xml
            pass

        self.attempt_to_set_url()

    def attempt_to_set_url(self):
        self.url = self.get_links()['self']['href']

    def url(self):
        return self.url

    def is_ok(self):
        """
        Returns true if the resource was provided from the server without
        error.  If the request to the server wasn't successfull for any
        reason, false is returned.
        """
        return self.get_field('stat') == 'ok'

    def get_keys(self):
        """
        Returns a list of the keys which comprise to this resource.
        """
        return self.data.keys()

    def get_fields(self):
        """
        Returns a list of the values contained within this resource.
        """
        return self.data.values()

    def get_field(self, key_list):
        """
        Attempts to retrieve the field mapped by the key_list.
        If there is no value found under the specified key_list an INVALID_KEY
        error is raised. 

        Parameters:
            key_list - the key(s) which map to a value to be obtained.
                       key_list can be a single (non-list) key, or any list
                       of keys to a set of nested dicts, in order of retrieval.
        
        Returns:
            The field mapped to by the key_list.
        """
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
            raise ResourceError(ResourceError.INVALID_KEY, '%s is not a valid '
                'key for this resource.' % key_list)
        else:
            return field

    def get_links(self):
        """
        Returns the links available to this resource.  This is equivilant to
        calling get_field('links').

        **NOTE**
            This method MUST be overridden for subclasses whose 'links' are
            not stored directly in the root of the resource.
        """
        try:
            return self.get_field('links')
        except ResourceError, e:
            raise ResourceError(ResourceError.INVALID_KEY, e.msg + \
                '  This is likely because you must use the resource object '
                'specific to this resource.')

    def get_link(self, link_name):
        try:
            link_list = self.get_links()
            return link_list[link_name]
        except KeyError, e:
            raise ResourceError(ResourceError.INVALID_KEY, 'The resource could'
                ' not retrieve the link %s' % link_name)

class ReviewRequest(Resource):
    """
    Class which specifically deals with /api/review-request/ type resources.
    """
    def __init__(self, resource, is_json=True):
        Resource.__init__(self, resource, is_json)

    def get_links(self):
        """
        Overriden specifically for a ReviewRequest.
        """
        return self.get_field(['review_request', 'links'])

    def draft_url(self):
        return self.get_link('draft')['href']

class DraftReviewRequest(Resource):
    """
    Class which specifically deals with /api/review-request/<num>/draft/ type
    resources.
    """
    def __init__(self, resource, is_json=True):
        Resource.__init__(self, resource, is_json)

    def get_links(self):
        """
        Overriden specifically for a DraftReviewRequest.
        """
        return self.get_field(['draft', 'links'])

