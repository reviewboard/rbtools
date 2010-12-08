#!/usr/bin/env python
import ServerInterface
import Resource
import urllib2
import os
import getpass

DEBUG = False
cookie = os.path.join('/home/lindsey/src/rbtools/rbtools/rbtools/', '.cookie.txt')
srvr = ServerInterface.ServerInterface(cookie)

def debug(str):
    if DEBUG:
        print ">>>> %s" % str

try:
    resp = srvr.post('http://demo.reviewboard.org/api/json/accounts/login/', {
        'username': raw_input('Username: '),
        'password': getpass.getpass('Password: ')
    })

    """
    #How to get session information:   
    resp = srvr.get('http://demo.reviewboard.org/api/session/')
    """
    """
    #How to get repositories:
    resp = srvr.get('http://demo.reviewboard.org/api/repositories/')
    """

    my_request = 'http://demo.reviewboard.org/api/review-requests/'
    data = {}

    data['submit_as'] = 'dionyses'
    data['repository'] = '2' 
    resp = srvr.post(my_request, data)
    debug(resp)
    new_review_request = Resource.ReviewRequest(resp)
    if new_review_request.is_ok():
        resp = srvr.put(new_review_request.draft_url(), {'summary': 'from client api thingy.  btw WOOO!'})
        debug(resp)
        draft_review_request = Resource.DraftReviewRequest(resp)
        if draft_review_request.is_ok():
            debug("draft successfully created")
            """
            do any other updates to the draft
            """
            pass
       
        try:
            resp = srvr.put(draft_review_request.url, {'public':'true'})
            debug(resp)
            draft_review_request = Resource.DraftReviewRequest(resp)
            if not draft_review_request.is_ok():
                debug("some error occurred making the draft public")
        except urllib2.HTTPError, e:
            if e.code == 303:
                #Do nothing, this is a web redirect which means everything worked!
                pass
            else:
                raise e       
 
        """
        say we want to close the request..
        """
        resp = srvr.put(new_review_request.url, {'status':'submitted'})
        debug(resp)
        new_review_request = Resource.ReviewRequest(resp)
        if not new_review_request.is_ok(): 
            debug("some error occurred closing the review request")

except urllib2.HTTPError, e:
    print e
    srvr.process_error(e.code, e.read())

except ServerInterface.APIError, e:
    print e

