import os

class RBUtilities:
	"""
	
	A Utility class that performs such tasks as finding out environment information, making system calls, and raising
	warnings and errors
	
	"""

	ERR_NO = 1

	log_file = None

	def __init__( self, log_file = 'rbproblems.log' ):
		"""__init__( self, log_file )
		
		Initializes the utility class
		
		Parameters:
			log_file, the file warnings and errors are logged in. set to None to prevent logging. DEFAULTS: 'rbproblems.log'
			
		"""
		
		self.log_file = log_file

	def system_call( self, call = '' ):
		"""sytem_call( self, call )
		
		Performs a system call. As of right now, this is merely using os.system
		
		Parameters:
			call, the call being executed. DEFAULTS: ''
			
		Returns: the response code
		
		"""
		
		return os.system( call )
		
	def output( self, text = '' ):
		"""output( self, text )
		
		outputs text
		
		Parameters:
			text, the text being outputted. Defaults: ''
			
		"""
		
		print text
		
	def raise_error( self, errorType = 'UnknownErrorType', errorMessage = 'No message', logError = True ):
		"""raise_error( self, errorType, errorMessage, logError )
		
		Logs and reports an error, then exits the program.
		NOTE: Under the default implementation, the only difference between an error and a warning,
			is that errors call exit afterward.
		
		Parameters
			errorType, the kind of error that has occurred. Defaults: 'UnknownErrorType'
			errorMessage, A message explaining what caused the error. Defaults: 'No message'
			logError, whether the error should be logged. Defaults: True
		
		"""
	
		output( 'Error-' + errorType + ': ' + errorMessage )

		if logError:
			file = open( self.log_file, 'a' )
			
			if not file:
				output( 'Further Error, could not open logfile (located at "' + self.log_file + '").' )
				exit(ERR_NO)
				
			file.write('Error,' + errorType + ',' + errorMessage)
			
			file.close()
		
	def raise_warning( self, warningType = 'UnknownWarningType', warningMessage = 'No message', logWarning = True ):
		"""raise_error( self, warningType, warningMessage, logWarning
		
		Logs and reports a warning.
		NOTE: Under the default implementation, the only difference between an error and a warning,
			is that errors call exit afterward.
		
		Parameters
			warningType, the kind of warning that has occurred. Defaults: 'UnknownErrorType'
			warningMessage, A message explaining what caused the warning. Defaults: 'No message'
			logWarning, whether the warning should be logged. Defaults: True
		
		"""
	
		output( 'Warning-' + warningType + ': ' + warningMessage )
		
		if logWarning:
			file = open( self.log_file, 'a' )
			
			if not file:
				output( 'Error, could not open logfile (located at "' + self.log_file + '").' )
				exit(ERR_NO)
				
			file.write('Error,' + warningType + ',' + warningMessage)
			
			file.close()