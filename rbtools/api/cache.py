import contextlib
import datetime
import json
import locale
import logging
import os
import sqlite3
import threading
from email.message import Message
from http.client import HTTPResponse
from typing import Callable, Dict, List, MutableMapping, Optional, Union
from urllib.request import urlopen, Request

from rbtools.api.errors import CacheError
from rbtools.deprecation import RemovedInRBTools50Warning
from rbtools.utils.appdirs import user_cache_dir


MINIMUM_VERSION = '2.0.14'  # Minimum server version to enable the API cache.

_locale_lock = threading.Lock()  # Lock for getting / setting locale.


class CacheEntry(object):
    """An entry in the API Cache."""

    DATE_FORMAT = '%Y-%m-%dT%H:%M:%S'  # ISO Date format

    def __init__(
        self,
        url: str,
        vary_headers: Dict[str, str],
        max_age: int,
        etag: str,
        local_date: datetime.datetime,
        last_modified: str,
        mime_type: str,
        item_mime_type: str,
        response_body: bytes,
    ) -> None:
        """Create a new cache entry.

        Args:
            url (str):
                The URL of the entry.

            vary_headers (dict):
                The resource's Vary header.

            max_age (int):
                The resource's maximum cache time, in seconds.

            etag (str):
                The resource's ETag.

            local_date (datetime.datetime):
                The local time when the cached resource was fetched.

            last_modified (str):
                The last modified date provided by the server.

            mime_type (str):
                The resource's Content-Type.

            item_mime_type (str):
                The resource's Item-Content-Type.

            response_body (bytes):
                The cached response body.
        """
        self.url = url
        self.vary_headers = vary_headers
        self.max_age = max_age
        self.etag = etag
        self.local_date = local_date
        self.last_modified = last_modified
        self.mime_type = mime_type
        self.item_mime_type = item_mime_type
        self.response_body = response_body

    def matches_request(
        self,
        request: Request,
    ) -> bool:
        """Determine if the cache entry matches the given request.

        This is done by comparing the value of the headers field to the
        headers in the request.

        Args:
            request (urllib.request.Request):
                The HTTP request to compare against.

        Returns:
            bool:
            ``True`` if the cache entry matches the request. ``False``
            otherwise.
        """
        if self.vary_headers:
            for header, value in self.vary_headers.items():
                if request.headers.get(header) != value:
                    return False

        return True

    def up_to_date(self) -> bool:
        """Determine if the cache entry is up to date.

        Version Changed:
            4.1:
            This now returns ``False`` if ``max_age`` is not available.

        Returns:
            bool:
            ``True`` if the cache entry is still valid. ``False``, otherwise.
        """
        if self.max_age is not None:
            max_age = datetime.timedelta(seconds=self.max_age)
            return self.local_date + max_age > datetime.datetime.now()

        return False


class LiveHTTPResponse(object):
    """An uncached HTTP response that can be read() more than once.

    This is intended to be API-compatible with an
    :py:class:`http.client.HTTPResponse` object. This allows a response to be
    read more than once.
    """

    def __init__(
        self,
        response: HTTPResponse,
    ) -> None:
        """Initialize the response.

        This will extract the data from the http.client response and store it.

        Args:
            response (http.client.HTTPResponse):
                The response from the server.
        """
        self.headers = response.info()
        self.content = response.read()
        self.status = response.status

    @property
    def code(self) -> int:
        """The HTTP response code.

        Type:
            int
        """
        return self.status

    def info(self) -> Message:
        """Return the headers associated with the response.

        Deprecated:
            4.0:
            Deprecated in favor of the :py:attr:`headers` attribute.

        Returns:
            email.message.Message:
            The response headers.
        """
        RemovedInRBTools50Warning.warn(
            'LiveHTTPResponse.info() is deprecated and will be removed in '
            'RBTools 5.0. Use LiveHTTPResponse.headers instead.')
        return self.headers

    def read(self) -> bytes:
        """Return the content associated with the response.

        Returns:
            bytes:
            The response content.
        """
        return self.content

    def getcode(self) -> int:
        """Return the associated HTTP response code.

        Deprecated:
            4.0:
            Deprecated in favor of the :py:attr:`code` attribute.

        Returns:
            int:
            The HTTP response code.
        """
        RemovedInRBTools50Warning.warn(
            'LiveHTTPResponseInfo.getcode() is deprecated and will be removed '
            'in RBTools 5.0. Use LiveHTTPResponse.code instead.')
        return self.status


class CachedHTTPResponse(object):
    """A response returned from the APICache.

    This is intended to be API-compatible with a urllib response object.
    """

    def __init__(
        self,
        cache_entry: CacheEntry,
    ) -> None:
        """Initialize the response.

        Args:
            cache_entry (CacheEntry):
                The cached data.
        """
        self.headers = {
            'Content-Type': cache_entry.mime_type,
            'Item-Content-Type': cache_entry.item_mime_type,
        }

        self.content = cache_entry.response_body
        self.status = 200

    @property
    def code(self) -> int:
        """The HTTP response code.

        Type:
            int
        """
        return self.status

    def info(self) -> dict:
        """Return the headers associated with the response.

        Deprecated:
            4.0:
            Deprecated in favor of the :py:attr:`headers` attribute.

        Returns:
            dict:
            The cached response headers.
        """
        RemovedInRBTools50Warning.warn(
            'CachedHTTPResponse.info() is deprecated and will be removed in '
            'RBTools 5.0. Use CachedHTTPResponse.headers instead.')
        return self.headers

    def read(self) -> bytes:
        """Return the content associated with the response.

        Returns:
            bytes:
            The cached response content.
        """
        return self.content

    def getcode(self) -> int:
        """Return the associated HTTP response code, which is always 200.

        Deprecated:
            4.0:
            Deprecated in favor of the :py:attr:`code` attribute.

        Returns:
            int:
            200, always. This pretends that the response is the successful
            result of an HTTP request.
        """
        RemovedInRBTools50Warning.warn(
            'CachedHTTPResponseInfo.getcode() is deprecated and will be '
            'removed in RBTools 5.0. Use CachedHTTPResponse.code instead.')
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

    def __init__(
        self,
        create_db_in_memory: bool = False,
        db_location: Optional[str] = None,
        urlopen: Optional[Callable] = None,
    ) -> None:
        """Create a new instance of the APICache

        If the db_path is provided, it will be used as the path to the SQLite
        database; otherwise, the default cache (in the CACHE_DIR) will be used.
        The urlopen parameter determines the method that is used to open URLs.

        Version Changed:
            4.0:
            Deprecated the ``urlopen`` parameter.

        Args:
            create_db_in_memory (bool, optional):
                Whether to store the API cache in memory, or persist to disk.

            db_location (str):
                The filename of the cache database, if using.

            urlopen (callable):
                The method to call for urlopen. This parameter has been
                deprecated.

        Raises:
            CacheError:
                The database exists but the schema could not be read.
        """
        if urlopen is not None:
            RemovedInRBTools50Warning.warn(
                'The urlopen parameter to APICache is deprecated and will be '
                'removed in RBTools 5.0.')

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

    def make_request(
        self,
        request: Request
    ) -> Union[LiveHTTPResponse, CachedHTTPResponse]:
        """Perform the specified request.

        If there is an up-to-date cached entry in our store, a CachedResponse
        will be returned. Otherwise, The urlopen method will be used to
        execute the request and a CachedResponse (if our entry is still up to
        date) or a Response (if it is not) will be returned.

        Args:
            request (urllib.request.Request):
                The HTTP request to perform.

        Returns:
            LiveHTTPResponse or CachedHTTPResponse:
            The response object.
        """
        if self.db is None or request.method != 'GET':
            # We can only cache HTTP GET requests and only if we were able to
            # access the API cache database.
            return LiveHTTPResponse(urlopen(request))

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

                response = LiveHTTPResponse(urlopen(request))

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
            response = LiveHTTPResponse(urlopen(request))
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

    def _get_caching_info(
        self,
        request_headers: MutableMapping[str, str],
        response_headers: Message,
    ) -> Optional[Dict]:
        """Get the caching info for the response to the given request.

        Args:
            request_headers (dict):
                The headers for the HTTP request.

            response_headers (email.message.Message):
                The headers for the HTTP response.

        Returns:
            dict:
            The information to use for the cache entry. May be ``None`` if the
            response cannot be cached.
        """
        max_age: Optional[int] = None
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

    def _create_schema(self) -> None:
        """Create the schema for the API cache database.

        Raises:
            CacheError:
                The database schema could not be created.
        """
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

    def _get_entry(
        self,
        request: Request,
    ) -> Optional[CacheEntry]:
        """Find an entry in the API cache store that matches the request.

        Args:
            request (urllib.request.Request):
                The HTTP request to check.

        Returns:
            CacheEntry:
            The matching cache entry. If there are no entries that match, this
            returns ``None``.

        Raises:
            CacheError:
                The entry could not be retrieved.
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

    def _save_entry(
        self,
        entry: CacheEntry,
    ) -> None:
        """Save the entry into the store.

        If the entry already exists in the store, do an UPDATE; otherwise do an
        INSERT. This does not commit to the database.

        Args:
            entry (CacheEntry):
                The cache entry to save.

        Raises:
            CacheError:
                The entry could not be saved.
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

    def _delete_entry(
        self,
        entry: CacheEntry,
    ) -> None:
        """Remove the entry from the store.

        Args:
            entry (CacheEntry):
                The entry to delete.

        Raises:
            CacheError:
                The entry could not be deleted.
        """
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
    def _row_factory(
        cursor: sqlite3.Cursor,
        row: sqlite3.Row,
    ) -> CacheEntry:
        """A factory for creating individual Cache Entries from db rows.

        Args:
            cursor (sqlite3.Cursor):
                The database cursor.

            row (sqlite3.Row):
                The database row.

        Returns:
            CacheEntry:
            The cache entry representing the row.
        """
        return CacheEntry(
            url=row[0],
            vary_headers=json.loads(row[1]),
            max_age=row[2],
            etag=row[3],
            local_date=datetime.datetime.strptime(
                row[4], CacheEntry.DATE_FORMAT),
            last_modified=row[5],
            mime_type=row[6],
            item_mime_type=row[7],
            response_body=bytes(row[8]))

    def _write_db(self) -> None:
        """Flush the contents of the DB to the disk.

        Raises:
            CacheError:
                The cache database could not be written.
        """
        if self.db:
            try:
                self.db.commit()
            except sqlite3.Error as e:
                self._die('Could not write database to disk', e)

    def _die(
        self,
        message: str,
        inner_exception: Exception,
    ) -> None:
        """Build an appropriate CacheError and raise it.

        Args:
            message (str):
                The message to include in the error.

            inner_exception (Exception):
                The exception to wrap.

        Raises:
            CacheError:
                The resulting exception.
        """
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

    def _split_csv(
        self,
        csvline: str,
    ) -> List[str]:
        """Split a line of comma-separated values into a list.

        Args:
            csvline (str):
                The line to split

        Returns:
            list of str:
            The split values.
        """
        return [
            s.strip()
            for s in csvline.split(',')
        ]


def clear_cache(cache_path: str = APICache.DEFAULT_CACHE_PATH) -> bool:
    """Delete the HTTP cache used for the API.

    Args:
        cache_path (str):
            The path of the cache database.

    Returns:
        bool:
        ``True`` if the operation succeeded. ``False``, otherwise.
    """
    try:
        os.unlink(cache_path)
        return True
    except Exception as e:
        logging.error('Could not clear cache in "%s": %s. Try manually '
                      'removing it if it exists.',
                      cache_path, e)
        return False
