#import API STUFF
	#RBUtilities

class Repository( object ):
	"""
	
	Repository is responsible with dealing with local repositories.
	It collects and stores info about the repository (location, SCM type, etc.)
	and creates diffs
	
	"""

	server_url = None	#the url of the server the local repository is tied to
	local_path = None	#the local path
	util = None			#Utility functions

	def __init__( self, server_url = None, util = RBUtilities.RBUtilities() ):
		"""__init__( self, server_url )
		
		Initializes the Repository object
		
		Parameters:
			server_url, the url of the ReviewBoard server the repository is tied to. DEFAULTS: None
			util, a class of utility functions. DEFAULTS RBUtilities.RBUtilities()
			
		"""
		
		#utilities are dealt with first, as problems in other parameters will cause util.raise_error/warning to be calleed
		if util is None:
			util = RBUtilities.RBUtilities()			
			util.raise_warning( "missingRequiredParameter", "Repository requires an RBUtilities. None dectected. Defaulting to RBUtilities (that is what is printing this warning)." )
		elif not isinstance( util, RBInterface.RBInterface()):
			util = RBUtilities.RBUtilities()
			util.raise_warning( "invalidTypeError", "Repository requires rb_interface RBUtilites, or a subtype thereof. Defaulting to RBUtilities (that is what is printing this warning).")	
		
		if server_url is None:
			util.raise_error( "missingRequiredParameter", "Repository needs to know the server url" )
			
		self.server_url = server_url
		self.util = util
		
		calculate_path()
		
	def calculate_path( self )
		"""calculate_local_path( self )
		
		calculates the path of the local repository, stores it to a variable
			
		Returns: the path
		
		"""
		
		local_path = None
		
		#do stuff
		
		self.local_path = local_path
		return local_path
		
	def create_diff( self, versions = None )
		"""create_path( self )
		
		Creates a diff of changes to the local repository
		
		Returns: the diff
		
		"""
		
		diff = None
		
		#do stuff
		
		return diff