from __future__ import print_function, unicode_literals

import contextlib
import datetime
import json
import locale
import logging
import os
import sqlite3
import threading

import six
from six.moves.urllib.request import urlopen

from rbtools.api.errors import CacheError
from rbtools.utils.appdirs import user_cache_dir


MINIMUM_VERSION = '2.0.14'  # Minimum server version to enable the API cache.

_locale_lock = threading.Lock()  # Lock for getting / setting locale.


class CacheEntry(object):
    """An entry in the API Cache."""

    DATE_FORMAT = '%Y-%m-%dT%H:%M:%S'  # ISO Date format

    def __init__(self, url, vary_headers, max_age, etag, local_date,
                 last_modified, mime_type, item_mime_type, response_body):
        """Create a new cache entry."""
        self.url = url
        self.vary_headers = vary_headers
        self.max_age = max_age
        self.etag = etag
        self.local_date = local_date
        self.last_modified = last_modified
        self.mime_type = mime_type
        self.item_mime_type = item_mime_type
        self.response_body = response_body

    def matches_request(self, request):
        """Determine if the cache entry matches the given request.

        This is done by comparing the value of the headers field to the
        headers in the request
        """
        if self.vary_headers:
            for header, value in six.iteritems(self.vary_headers):
                if request.headers.get(header) != value:
                    return False

        return True

    def up_to_date(self):
        """Determine if the cache entry is up to date."""
        if self.max_age is not None:
            max_age = datetime.timedelta(seconds=self.max_age)
            return self.local_date + max_age > datetime.datetime.now()

        return True


class HTTPResponse(object):
    """An uncached HTTP response that can be read() more than once.

    This is intended to be API-compatible with a urllib2 response object. This
    allows a response to be read more than once.
    """
    def __init__(self, response):
        """Extract the data from a urllib2 HTTP response."""
        self.headers = response.info()
        self.content = response.read()
        self.code = response.getcode()

    def info(self):
        """Get the headers associated with the response."""
        return self.headers

    def read(self):
        """Get the content associated with the response."""
        return self.content

    def getcode(self):
        """Get the associated HTTP response code."""
        return self.code


class CachedHTTPResponse(object):
    """A response returned from the APICache.

    This is intended to be API-compatible with a urllib2 response object.
    """
    def __init__(self, cache_entry):
        """Create a new CachedResponse from the given CacheEntry."""
        self.headers = {
            'Content-Type': cache_entry.mime_type,
            'Item-Content-Type': cache_entry.item_mime_type,
        }

        self.content = cache_entry.response_body

    def info(self):
        """Get the headers associated with the response."""
        return self.headers

    def read(self):
        """Get the content associated with the response."""
        return self.content

    def getcode(self):
        """Get the associated HTTP response code, which is always 200.

        This method returns 200 because it is pretending that it made a
        successful HTTP request.
        """
        return 200


class APICache(object):
    """An API cache backed by a SQLite database."""

    # The format for the Expires: header. Requires an English locale.
    EXPIRES_FORMAT = '%a, %d %b %Y %H:%M:%S %Z'

    DEFAULT_CACHE_DIR = user_cache_dir('rbtools')
    DEFAULT_CACHE_PATH = os.path.join(DEFAULT_CACHE_DIR, 'apicache.db')

    # The API Cache's schema version. If the schema is updated, update this
    # value.
    SCHEMA_VERSION = 2

    def __init__(self, create_db_in_memory=False, db_location=None,
                 urlopen=urlopen):
        """Create a new instance of the APICache

        If the db_path is provided, it will be used as the path to the SQLite
        database; otherwise, the default cache (in the CACHE_DIR) will be used.
        The urlopen parameter determines the method that is used to open URLs.
        """
        self.urlopen = urlopen

        if create_db_in_memory:
            logging.debug('Creating API cache in memory.')

            self.db = sqlite3.connect(':memory:')
            self.cache_path = None
            self._create_schema()
        else:
            self.cache_path = db_location or self.DEFAULT_CACHE_PATH

            try:
                cache_exists = os.path.exists(self.cache_path)
                create_schema = True

                if not cache_exists:
                    cache_dir = os.path.dirname(self.cache_path)

                    if not os.path.exists(cache_dir):
                        logging.debug('Cache directory "%s" does not exist; '
                                      'creating.',
                                      cache_dir)
                        os.makedirs(cache_dir)

                    logging.debug('API cache "%s" does not exist; creating.',
                                  self.cache_path)

                self.db = sqlite3.connect(self.cache_path)

                if cache_exists:
                    try:
                        with contextlib.closing(self.db.cursor()) as c:
                            c.execute('SELECT version FROM cache_info')
                            row = c.fetchone()

                            if row and row[0] == self.SCHEMA_VERSION:
                                create_schema = False
                    except sqlite3.Error as e:
                        self._die(
                            'Could not get the HTTP cache schema version', e)

                if create_schema:
                    self._create_schema()
            except (OSError, sqlite3.Error):
                # OSError will be thrown if we cannot create the directory or
                # file for the API cache. sqlite3.Error will be thrown if
                # connect fails. In either case, HTTP requests can still be
                # made, they will just passed through to the URL opener without
                # attempting to interact with the API cache.
                logging.warn('Could not create or access API cache "%s". Try '
                             'running "rbt clear-cache" to clear the HTTP '
                             'cache for the API.',
                             self.cache_path)

        if self.db is not None:
            self.db.row_factory = APICache._row_factory

    def make_request(self, request):
        """Perform the specified request.

        If there is an up-to-date cached entry in our store, a CachedResponse
        will be returned. Otherwise, The urlopen method will be used to
        execute the request and a CachedResponse (if our entry is still up to
        date) or a Response (if it is not) will be returned.
        """
        if self.db is None or request.method != 'GET':
            # We can only cache HTTP GET requests and only if we were able to
            # access the API cache database.
            return self.urlopen(request)

        entry = self._get_entry(request)

        if entry:
            if entry.up_to_date():
                logging.debug('Cached response for HTTP GET %s up to date',
                              request.get_full_url())
                response = CachedHTTPResponse(entry)
            else:
                if entry.etag:
                    request.add_header('If-none-match', entry.etag)

                if entry.last_modified:
                    request.add_header('If-modified-since',
                                       entry.last_modified)

                response = HTTPResponse(self.urlopen(request))

                if response.getcode() == 304:
                    logging.debug('Cached response for HTTP GET %s expired '
                                  'and was not modified',
                                  request.get_full_url())
                    entry.local_date = datetime.datetime.now()
                    self._save_entry(entry)
                    response = CachedHTTPResponse(entry)
                elif 200 <= response.getcode() < 300:
                    logging.debug('Cached response for HTTP GET %s expired '
                                  'and was modified',
                                  request.get_full_url())
                    response_headers = response.info()
                    cache_info = self._get_caching_info(request.headers,
                                                        response_headers)

                    if cache_info:
                        entry.max_age = cache_info['max_age']
                        entry.etag = cache_info['etag']
                        entry.local_date = datetime.datetime.now()
                        entry.last_modified = cache_info['last_modified']

                        entry.mime_type = response_headers['Content-Type']
                        entry.item_mime_type = \
                            response_headers.get('Item-Content-Type')
                        entry.response_body = response.read()

                        if entry.vary_headers != cache_info['vary_headers']:
                            # The Vary: header has changed since the last time
                            # we retrieved the resource so we need to remove
                            # the old cache entry and save the new one.
                            self._delete_entry(entry)
                            entry.vary_headers = cache_info['vary_headers']

                        self._save_entry(entry)
                    else:
                        # This resource is no longer cache-able so we should
                        # delete our cached version.
                        logging.debug('Cached response for HTTP GET request '
                                      'to %s is no longer cacheable',
                                      request.get_full_url())
                        self._delete_entry(entry)
        else:
            response = HTTPResponse(self.urlopen(request))
            response_headers = response.info()

            cache_info = self._get_caching_info(request.headers,
                                                response_headers)

            if cache_info:
                self._save_entry(CacheEntry(
                    request.get_full_url(),
                    cache_info['vary_headers'],
                    cache_info['max_age'],
                    cache_info['etag'],
                    datetime.datetime.now(),
                    cache_info['last_modified'],
                    response_headers.get('Content-Type'),
                    response_headers.get('Item-Content-Type'),
                    response.read()))

                logging.debug('Added cache entry for HTTP GET request to %s',
                              request.get_full_url())

            else:
                logging.debug('HTTP GET request to %s cannot be cached',
                              request.get_full_url())

        return response

    def _get_caching_info(self, request_headers, response_headers):
        """Get the caching info for the response to the given request.

        A dictionary with caching information is returned, or None if the
        response cannot be cached.
        """
        max_age = None
        no_cache = False

        expires = response_headers.get('Expires')

        if expires:
            # We switch to the C locale to parse the 'Expires' header because
            # the formatting specifiers are locale specific and the header
            # *must* be provided in English. After parsing the header, we
            # restore the locale to the user's previous locale.
            #
            # We also note that changing the locale is not thread-safe so we
            # use a lock around this.
            with _locale_lock:
                old_locale = locale.setlocale(locale.LC_TIME)

                try:
                    # 'setlocale' requires the second parameter to be a 'str'
                    # in both Python 2.x and Python 3+.
                    locale.setlocale(locale.LC_TIME, str('C'))
                    expires = datetime.datetime.strptime(expires,
                                                         self.EXPIRES_FORMAT)

                    # We assign to max_age because the value of max-age in the
                    # Cache-Control header overrides the behaviour of the
                    # 'Expires' header.
                    now = datetime.datetime.now()

                    if expires < now:
                        max_age = 0
                    else:
                        max_age = (expires - now).seconds
                except ValueError:
                    logging.error('The format of the "Expires" header (value '
                                  '%s) does not match the expected format.',
                                  expires)
                except locale.Error:
                    logging.error('The C locale is unavailable on this '
                                  'system. The "Expires" header cannot be '
                                  'parsed.')
                finally:
                    locale.setlocale(locale.LC_TIME, old_locale)

        # The value of the Cache-Control header is a list of comma separated
        # values. We only care about some of them, notably max-age, no-cache,
        # no-store, and must-revalidate. The other values are only applicable
        # to intermediaries.
        for kvp in self._split_csv(response_headers.get('Cache-Control', '')):
            if kvp.startswith('max-age'):
                max_age = int(kvp.split('=')[1].strip())
            elif kvp.startswith('no-cache'):
                # The no-cache specifier optionally has an associated header
                # that we shouldn't cache. However, the *only* headers we are
                # caching are headers that describe the the cached content:
                # Content-Type, and Item-Content-Type.
                no_cache = True
            elif kvp == 'no-store':
                # If no-store is specified, we cannot cache anything about this
                # resource.
                return None
            elif kvp == 'must-revalidate':
                # We treat must-revalidate identical to no-cache because we are
                # not an intermediary.
                no_cache = True

        # The Pragma: header is an obsolete header that may contain the value
        # no-cache, which is equivalent to Cache-Control: no-cache. We check
        # for it for posterity's sake.
        if 'no-cache' in response_headers.get('Pragma', ''):
            no_cache = True

        etag = response_headers.get('ETag')
        last_modified = response_headers.get('Last-Modified')
        vary_headers = response_headers.get('Vary')

        # The Vary header specifies a list of headers that *may* alter the
        # returned response. The cached response can only be used when these
        # headers have the same value as those provided in the request.
        if vary_headers:
            vary_headers = dict(
                (header, request_headers.get(header))
                for header in self._split_csv(vary_headers)
            )
        else:
            vary_headers = {}

        if no_cache:
            # If no-cache is specified, the resource must always be requested,
            # so we will treat this as if the max_age is zero.
            max_age = 0

        if no_cache and not etag and not last_modified:
            # We have no information with which to provide the server to check
            # if our content is up to date. Therefore, the information cannot
            # be cached.
            return None

        return {
            'max_age': max_age,
            'etag': etag,
            'last_modified': last_modified,
            'vary_headers': vary_headers
        }

    def _create_schema(self):
        """Create the schema for the API cache database."""
        try:
            with contextlib.closing(self.db.cursor()) as c:
                c.execute('DROP TABLE IF EXISTS api_cache')
                c.execute('DROP TABLE IF EXISTS cache_info')

                c.execute('''CREATE TABLE api_cache(
                                 url            TEXT,
                                 vary_headers   TEXT,
                                 max_age        INTEGER,
                                 etag           TEXT,
                                 local_date     TEXT,
                                 last_modified  TEXT,
                                 mime_type      TEXT,
                                 item_mime_type TEXT,
                                 response_body  BLOB,
                                 PRIMARY KEY(url, vary_headers)
                             )''')

                c.execute('CREATE TABLE cache_info(version INTEGER)')

                c.execute('INSERT INTO cache_info(version) VALUES(?)',
                          (self.SCHEMA_VERSION,))

            self._write_db()
        except sqlite3.Error as e:
            self._die('Could not create database schema for the HTTP cache', e)

    def _get_entry(self, request):
        """Find an entry in the API cache store that matches the request.

        If no such cache entry exists, this returns None.
        """
        url = request.get_full_url()

        try:
            with contextlib.closing(self.db.cursor()) as c:
                for row in c.execute('SELECT * FROM api_cache WHERE url=?',
                                     (url,)):
                    if row.matches_request(request):
                        return row
        except sqlite3.Error as e:
            self._die('Could not retrieve an entry from the HTTP cache', e)

        return None

    def _save_entry(self, entry):
        """Save the entry into the store.

        If the entry already exists in the store, do an UPDATE; otherwise do an
        INSERT. This does not commit to the database.
        """
        vary_headers = json.dumps(entry.vary_headers)
        local_date = entry.local_date.strftime(entry.DATE_FORMAT)

        try:
            with contextlib.closing(self.db.cursor()) as c:
                try:
                    c.execute('''INSERT INTO api_cache (url,
                                                        vary_headers,
                                                        max_age,
                                                        etag,
                                                        local_date,
                                                        last_modified,
                                                        mime_type,
                                                        item_mime_type,
                                                        response_body)
                                 VALUES(?,?,?,?,?,?,?,?,?)''',
                              (entry.url, vary_headers, entry.max_age,
                               entry.etag, local_date, entry.last_modified,
                               entry.mime_type, entry.item_mime_type,
                               sqlite3.Binary(entry.response_body)))
                except sqlite3.IntegrityError:
                    c.execute('''UPDATE api_cache
                                 SET max_age=?,
                                     etag=?,
                                     local_date=?,
                                     last_modified=?,
                                     mime_type=?,
                                     item_mime_type=?,
                                     response_body=?
                                 WHERE url=? AND vary_headers=?''',
                              (entry.max_age, entry.etag, local_date,
                               entry.last_modified, entry.mime_type,
                               entry.item_mime_type,
                               sqlite3.Binary(entry.response_body), entry.url,
                               vary_headers))

            self._write_db()
        except sqlite3.Error as e:
            self._die('Could not write entry to the HTTP cache for the API', e)

    def _delete_entry(self, entry):
        """Remove the entry from the store."""
        try:
            with contextlib.closing(self.db.cursor()) as c:
                c.execute(
                    'DELETE FROM api_cache WHERE URL=? AND vary_headers=?',
                    (entry.url, json.dumps(entry.vary_headers)))

            self._write_db()
        except sqlite3.Error as e:
            self._die('Could not delete entry from the HTTP cache for the API',
                      e)

    @staticmethod
    def _row_factory(cursor, row):
        """A factory for creating individual Cache Entries from db rows."""
        return CacheEntry(
            url=row[0],
            vary_headers=json.loads(row[1]),
            max_age=row[2],
            etag=row[3],
            local_date=datetime.datetime.strptime(row[4],
                                                  CacheEntry.DATE_FORMAT),
            last_modified=row[5],
            mime_type=row[6],
            item_mime_type=row[7],
            response_body=six.binary_type(row[8]),
        )

    def _write_db(self):
        """Flush the contents of the DB to the disk."""
        if self.db:
            try:
                self.db.commit()
            except sqlite3.Error as e:
                self._die('Could not write database to disk', e)

    def _die(self, message, inner_exception):
        """Build an appropriate CacheError and raise it."""
        message = '%s: %s.' % (message, inner_exception)

        if self.cache_path:
            if self.cache_path == APICache.DEFAULT_CACHE_PATH:
                cache_args = ''
            else:
                cache_args = ' --cache-location %s' % self.cache_path

            message += (' Try running "rbt clear-cache%s" to manually clear '
                        'the HTTP Cache for the API.'
                        % cache_args)

        raise CacheError(message)

    def _split_csv(self, csvline):
        """Split a line of comma-separated values into a list."""
        return [
            s.strip()
            for s in csvline.split(',')
        ]


def clear_cache(cache_path=APICache.DEFAULT_CACHE_PATH):
    """Delete the HTTP cache used for the API."""
    try:
        os.unlink(cache_path)
        print('Cleared cache in "%s"' % cache_path)
    except Exception as e:
        logging.error('Could not clear cache in "%s": %s. Try manually '
                      'removing it if it exists.',
                      cache_path, e)
