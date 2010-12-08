import urllib2

#import API STUFF
	#APIError
	#RBInterface
import RBUtilities
import Repository

class ServerManager( object ):
	"""
	
	ServerManager is the class responsible for handling server/client interactions.
	It is responsible for authenticating with ReviewBoard servers, and creating
	requests (such as new reviews, diffs, etc. ). It uses an RBInterface to make
	its REST (POST, GET, DELETE, etc. ) calls, and also for storing passwords
	
	"""

	LOGIN_PATH = 'api/json/accounts/login/'

	rb_interface = None			#Interfaces directly with the ReviewBoard server
	default_repository = None	#Default repository 
	util = None					#Utility functions
	
	def __init__( self, rb_interface = RBInterface.RBInterface(), default_repository = None, password_manager = urllib2.HTTPPasswordMgr, util = RBUtilities.RBUtilities() ):
		"""__init( self, rb_interface, default_repository, password_mgr, util )
		
		Initiates a new ServerManager Object
		
		Parameters:
			rb_interface, Interface that directly talks to the server. DEFAULTS: RBInterface.RBInterface()
			default_repository, A repository object. DEFAULTS: None
			password_manager, the password manager. Defaults: urllib2.HTTPPasswordMgr
			util, A class of utility functions. DEFAULTS: RBUtilities.RBUtilities
		
		"""
		
		#utilities are dealt with first, as problems in other parameters will cause util.raise_error/warning to be calleed
		if util is None:
			util = RBUtilities.RBUtilities()			
			util.raise_warning( "missingRequiredParameter", "ServerManager requires an RBUtilities. None dectected. Defaulting to RBUtilities (that is what is printing this warning)." )
		elif not isinstance( util, RBInterface.RBInterface()):
			util = RBUtilities.RBUtilities()
			util.raise_warning( "invalidTypeError", "ServerManager requires rb_interface RBUtilites, or a subtype thereof. Defaulting to RBUtilities (that is what is printing this warning).")	
		
		if rb_interface is None:
			util.raise_error( "missingRequiredParameter", "ServerManager requires an RBInterface. None dectected." )
		elif not isinstance( rb_interface, RBInterface.RBInterface()):
			util.raise_error( "invalidTypeError", "ServerManager requires rb_interface to be an RBInterface, or a subtype thereof.")
		
		if password_manager is None:
			util.raise_error("missingRequiredParameter", "ServerManager requires a password manager. None detected." )
		
		self.rb_interface = rb_interface
		self.password_manager = password_manager
		self.util = util
		
		set_default_repository( default_repository )
		
	def set_default_repository( self, default_repository = None ):
		"""set_default_repository( self, default_repository )
		
		Sets the default local repository to use in server communications
		
		Parameters:
			default_repository, the repository to set default to, DEFAULTS: none
			
		"""
		
		if local_repository is None:
			self.util.raise_warning( "NoDefault", "No default value set for the local repository" )
		elif  not isinstance( default_repository, Repository ):
			self.util.raise_error( "InvalidTypeError", "Servermanager requires the local repository to be a Repository, or as subtype thereof")

		self.local_repository = local_repository
		
	def login( self, rb_user = None, rb_password = None, force = False, repo = None ):
		"""login( self, rb_user, rb_password, force, repo )
		
		Logs into a ReviewBoard server
		
		Parameters:
			force, whether or not to force entering of credentials (i.e. don't use cookie). Defaults: False
			rb_user, The username. If None, the user will be prompted Defaults: None
			rb_password, The password. If None, the user will be prompted Defaults: None
			repo, the repository to log into. If None, defaults to default_repository. Defaults: None
		
		Returns: True/False whether login was successful
		
		"""
		logged_in = False
		
		if repo is None:
			repo = self.default_repository
		
		if not force and not self.rb_interface.has_valid_cookie( repo.server_url ):
			util.output( "==>Connecting to Review Board at: " + repo.server_url )
			
			if not rb_password or not rb_user:
				if rb_user:
					util.output( "Username: " + rb_user )
				else
					rb_user = util.input( "Username: " )
				
				if not rb_password:
					rb_password = util.input( "Password: ", True )
					
			try
				rb_interface.post( LOGIN_PATH, { 'username': rb_user, 'password': rb_password })
				
				logged_in = True
			except APIError, e:
				util.raise_error( "LoginFailed", e )
				
		else:
			logged_in = True #what needs to be done if there is a cookie?
		
		return logged_in
		
	def create_review_request( self, repo = None ):
		"""create_review_request( self, repo ):
		
		Creates a ReviewRequest object that can be used to request  the creation of a new review
		
		Parameters:
			repo, the local repository to be used. If None, default_repository will be used instead. DEFAULTS: None
			
		Returns: the new ReviewRequest (or None if an issue comes up
		
		"""
		
		new_review_cls = None
		
		#do stuff here
		
		return new_request_cls
		
	def get_review_request( self, review_id = None, repo = None )
	
		get_review_cls = None
		
		#do stuff here
		
		return get_review_cls