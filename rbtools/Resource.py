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
    def __init__(self, url, resource, is_json=True):
        self.url = url
        self.resource = resource
        self.is_json = is_json
        self.data = {}

        if is_json:
            self.data = json_loads(self.resource)
        else:
            #Preform deserialization for xml
            pass

    def get_keys(self):
        return self.data.keys()

    def get_fields(self):
        return self.data.values()

    def get_field(self, key_list):
        """
        Attempts to retrieve the field mapped by the key_list.  Key list can be
        a single (non-list) key, or any list of keys in order of retrieval.
        If there is no value found under the specified key_list an INVALID_KEY
        error is raised. 
        """
        if isinstance(key_list, list):
            field = self.data.get(key_list[0])
            
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
        try:
            return self.get_field('links')
        except ResourceError, e:
            raise ResourceError(ResourceError.INVALID_KEY, e.msg + \
                '  This is likely because you must use the resource object '
                'specific to this resource.')


class ReviewRequestResource(Resource):
    """
    Class which specifically deals with review-request type resources.
    """
    def __init__(self, url, resource, is_json=True):
        Resource(self, url, resource, is_json)

    def get_links(self):
        return self.get_field(['review-request', 'links'])

    def get_link(self, link_name):
        try:
            link_list = self.get_links()
            return link_list[link_name]
        except KeyError, e:
            raise ResourceError(ResourceError.INVALID_KEY, 'The resource could'
                ' not retrieve the link %s' % link_name)



class ResourceHandler(object):
    def __init__(self, resource, server_interface):
        self.resource = resource
        self.server_interface = server_interface
    
    def parent(self):
        """
        try:
            resource = server_interface.get(Utils.path_up_one(resource.url))
        except ServerInterfaceError
        except UtilsError
        """
        pass

    def set_field(self, key, value):
        rsp = self.server_interface.put(self.resource.url, {key:value})    


