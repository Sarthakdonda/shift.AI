"""Per-application MongoDB Atlas provisioning.

Every generated application that needs cloud records gets its own database, its
own database user and its own generated password on the *application* cluster.
The platform's own database is never reachable from a generated application:

  APP_ATLAS_URI cluster        MONGODB_URI cluster
    shift_app_<id>  <- app        <platform db>  <- shift.AI only

A connection string cannot create users, so provisioning needs an Atlas
Administration API key pair (ATLAS_PUBLIC_KEY / ATLAS_PRIVATE_KEY) and the
project id. Without them this module refuses to provision rather than sharing
the powerful cluster credential with a generated application.

The resulting URI is encrypted at rest with the platform session secret and is
only ever handed to the backend host as an environment variable. It is never
returned to the browser.
"""
import re
import secrets
import string
import threading
import time
from urllib.parse import quote, urlsplit
import httpx
from pymongo import MongoClient
from pymongo.errors import PyMongoError
from app.core.config import get_settings
from app.core.errors import AppError
from app.repositories.store import now
from app.services.account_security import cipher

API = 'https://cloud.mongodb.com/api/atlas/v2'
TOKEN_URL = 'https://cloud.mongodb.com/api/oauth/token'
# Versioned Atlas API: the resource version must be requested explicitly.
ACCEPT = 'application/vnd.atlas.2023-02-01+json'
# Atlas rejects usernames outside this shape; keep identifiers boring and short.
SAFE = re.compile(r'^[a-z0-9_]{6,48}$')
PASSWORD_ALPHABET = string.ascii_letters + string.digits
# Service-account access tokens last an hour; refresh a little early.
_token = {'value': '', 'expires': 0.0}
_token_lock = threading.Lock()


def _service_account():
    s = get_settings()
    return bool(s.atlas_service_client_id and s.atlas_service_client_secret)


def _bearer():
    """Client-credentials token for an Atlas service account, cached until expiry."""
    s = get_settings()
    with _token_lock:
        if _token['value'] and _token['expires'] > time.monotonic():
            return _token['value']
        try:
            result = httpx.post(TOKEN_URL, data={'grant_type': 'client_credentials'},
                                auth=(s.atlas_service_client_id, s.atlas_service_client_secret),
                                headers={'Accept': 'application/json'}, timeout=30, trust_env=False)
        except httpx.HTTPError:
            raise AppError('The Atlas token endpoint is unreachable. Check network access, then retry.',
                           502, 'atlas_provider') from None
        if not result.is_success:
            raise AppError('Atlas rejected the service account (HTTP ' + str(result.status_code)
                           + '). Confirm ATLAS_SERVICE_CLIENT_ID/SECRET and that the service account has '
                             'Project Owner on the application project.', 502, 'atlas_provider')
        body = result.json()
        _token['value'] = body['access_token']
        _token['expires'] = time.monotonic() + max(60, int(body.get('expires_in', 3600)) - 120)
        return _token['value']


def _auth_kwargs():
    """Bearer for a service account, HTTP digest for a legacy API key pair."""
    s = get_settings()
    if _service_account():
        return {'headers': {'Accept': ACCEPT, 'Content-Type': ACCEPT,
                            'Authorization': 'Bearer ' + _bearer()}}
    return {'headers': {'Accept': ACCEPT, 'Content-Type': ACCEPT},
            'auth': httpx.DigestAuth(s.atlas_public_key, s.atlas_private_key)}


def configured():
    """True when a per-application database can actually be created."""
    s = get_settings()
    credentials = _service_account() or (s.atlas_public_key and s.atlas_private_key)
    return bool(s.app_atlas_uri.strip() and credentials and s.atlas_project_id and s.atlas_cluster_name)


def requirements():
    """Exactly which settings are still missing, for an actionable error."""
    s = get_settings()
    missing = [name for name, value in (
        ('APP_ATLAS_URI', s.app_atlas_uri.strip()),
        ('ATLAS_SERVICE_CLIENT_ID or ATLAS_PUBLIC_KEY', s.atlas_service_client_id or s.atlas_public_key),
        ('ATLAS_SERVICE_CLIENT_SECRET or ATLAS_PRIVATE_KEY', s.atlas_service_client_secret or s.atlas_private_key),
        ('ATLAS_PROJECT_ID', s.atlas_project_id), ('ATLAS_CLUSTER_NAME', s.atlas_cluster_name)) if not value]
    return missing


def require():
    missing = requirements()
    if missing:
        raise AppError('Cloud database provisioning needs ' + ', '.join(missing)
                       + ' in backend/.env. Create an Atlas service account (or Administration API key) with '
                         'Project Owner on the application project, then restart the backend.',
                       503, 'atlas_configuration')


def _cluster_host():
    """Host portion of the application cluster, without any credentials."""
    uri = get_settings().app_atlas_uri.strip()
    if ' ' in uri:
        raise AppError('APP_ATLAS_URI contains a space. Put the connection string on one line '
                       'and percent-encode any reserved character in the password.', 503, 'atlas_configuration')
    if not uri.startswith('mongodb+srv://'):
        raise AppError('APP_ATLAS_URI must be an Atlas mongodb+srv connection string.', 503, 'atlas_configuration')
    host = urlsplit(uri).netloc.split('@')[-1]
    if not host:
        raise AppError('APP_ATLAS_URI is missing its cluster host.', 503, 'atlas_configuration')
    return host


def _error(result):
    try:
        body = result.json() if result.content else {}
    except ValueError:
        body = {}
    return str(body.get('errorCode', '')), str(body.get('detail', ''))[:180]


def api(method, path, body=None, attempts=6):
    """One Atlas Administration API call.

    A rejection by the API access list or the rate limiter happens before the
    request is processed, so retrying it is safe for any method. Some networks
    egress from several public addresses, and only some may be allowlisted.
    """
    result = None
    refreshed = False
    for attempt in range(attempts):
        try:
            auth = _auth_kwargs()
            result = httpx.request(method, API + path, json=body, timeout=30, follow_redirects=False,
                                   trust_env=False, **auth)
            if result.status_code == 401 and _service_account() and not refreshed:
                # Authentication rejection precedes processing. Refresh once, including
                # tokens revoked before their advertised expiry; never loop on bad credentials.
                refreshed = True
                rejected = auth['headers']['Authorization']
                with _token_lock:
                    if rejected == 'Bearer ' + _token['value']:
                        _token.update(value='', expires=0.0)
                result = httpx.request(method, API + path, json=body, timeout=30, follow_redirects=False,
                                       trust_env=False, **_auth_kwargs())
        except httpx.HTTPError:
            if attempt + 1 >= attempts:
                raise AppError('Atlas Administration API is unreachable. Check network access, then retry.',
                               502, 'atlas_provider') from None
            time.sleep(min(8.0, 1.5 * (attempt + 1)))
            continue
        code, _ = _error(result)
        unprocessed = result.status_code == 429 or (result.status_code == 403 and code == 'IP_ADDRESS_NOT_ON_ACCESS_LIST')
        if unprocessed and attempt + 1 < attempts:
            time.sleep(min(8.0, 1.5 * (attempt + 1)))
            continue
        break
    code, detail = _error(result)
    if result.status_code == 403 and code == 'IP_ADDRESS_NOT_ON_ACCESS_LIST':
        raise AppError('Atlas refused this server\'s address: ' + detail + ' Add it to the service account\'s API '
                       'access list. Networks that egress from several addresses need every one of them listed.',
                       502, 'atlas_access_list')
    if result.status_code == 429:
        raise AppError('Atlas rate limit reached. Retry shortly.', 429, 'atlas_rate_limited')
    if result.status_code == 403 and code == 'USER_UNAUTHORIZED' and '/databaseUsers' in path:
        raise AppError('Atlas denied database-user management. Give the deployment service account '
                       'Project Database Access Admin on the application project (or Project Owner for '
                       'the full deployment setup). Project Data Access Admin does not grant this permission.',
                       502, 'atlas_permissions')
    if result.status_code in (401, 403):
        reason = ' (' + code + ')' if re.fullmatch(r'[A-Z0-9_]{1,80}', code) else ''
        raise AppError('Atlas rejected the Administration API request' + reason + '. Confirm the service account or key '
                       'pair, its project access, and that the calling IP is on the API access list.',
                       502, 'atlas_provider')
    if result.status_code == 404:
        raise AppError('Atlas project or cluster was not found. Check ATLAS_PROJECT_ID and ATLAS_CLUSTER_NAME.',
                       502, 'atlas_provider')
    if not result.is_success and result.status_code != 409:
        raise AppError('Atlas returned HTTP ' + str(result.status_code) + '. ' + detail, 502, 'atlas_provider')
    if not result.content:
        return {}
    try:
        return result.json()
    except ValueError:
        return {}


def identifiers(application_id):
    """Stable, unique and Atlas-safe database and user names for one application."""
    token = re.sub(r'[^a-f0-9]', '', str(application_id).lower())[-12:] or secrets.token_hex(6)
    prefix = re.sub(r'[^a-z0-9_]', '', get_settings().app_atlas_database_prefix.lower()) or 'shift_app_'
    database = (prefix + token)[:38]
    username = ('app_' + token)[:38]
    if not SAFE.match(database) or not SAFE.match(username):
        raise AppError('Generated database identifiers are invalid.', 500)
    return database, username


def password():
    return ''.join(secrets.choice(PASSWORD_ALPHABET) for _ in range(40))


def connection_uri(username, secret, database):
    """A URI scoped to one database, built from the cluster host only."""
    return ('mongodb+srv://' + quote(username, safe='') + ':' + quote(secret, safe='')
            + '@' + _cluster_host() + '/' + database + '?retryWrites=true&w=majority')


def _user_body(username, secret, database):
    return {'databaseName': 'admin', 'username': username, 'password': secret,
            'roles': [{'databaseName': database, 'roleName': 'readWrite'}],
            'scopes': [{'name': get_settings().atlas_cluster_name, 'type': 'CLUSTER'}]}


def _update_user(username, secret, database):
    """Reset the password and re-assert the scope of an existing user."""
    body = _user_body(username, secret, database)
    api('PATCH', '/groups/' + get_settings().atlas_project_id + '/databaseUsers/admin/' + username,
        {'password': secret, 'roles': body['roles'], 'scopes': body['scopes']})


def _upsert_user(username, secret, database):
    """Create the user, or reset its password when Atlas reports a conflict."""
    body = _user_body(username, secret, database)
    created = api('POST', '/groups/' + get_settings().atlas_project_id + '/databaseUsers', body)
    if created.get('username') != username:
        _update_user(username, secret, database)


def initialise(uri, database, indexes=()):
    """Prove the scoped credential works, then create the requested indexes."""
    try:
        client = MongoClient(uri, serverSelectionTimeoutMS=15000, connectTimeoutMS=15000)
        db = client[database]
        db.command('ping')
        db['_shift_meta'].update_one({'_id': 'provisioned'},
                                     {'$set': {'provisioned_at': now(), 'schema_version': 1}}, upsert=True)
        for collection, keys, unique in indexes:
            db[collection].create_index(list(keys), unique=bool(unique))
        client.close()
    except PyMongoError as exc:
        raise AppError('The new database user could not connect to its database (' + type(exc).__name__
                       + '). Check the Atlas IP access list for this cluster, then retry.',
                       502, 'atlas_provider') from None


def _network(entry):
    import ipaddress
    try:
        return ipaddress.ip_network(entry.strip(), strict=False)
    except ValueError:
        raise AppError('Invalid network address: ' + str(entry)[:60], 502, 'atlas_provider') from None


def access_entries():
    """The project's current database network access list (not the API access list)."""
    require()
    rows = api('GET', '/groups/' + get_settings().atlas_project_id + '/accessList?itemsPerPage=500')
    return [row.get('cidrBlock') or (row.get('ipAddress', '') + '/32') for row in (rows or {}).get('results', [])]


def ensure_access(entries, comment):
    """Allow backend outbound ranges to reach the cluster.

    Idempotent: entries already covered are skipped, unrelated entries are never
    touched, and open-internet ranges are refused outright.
    """
    require()
    wanted = []
    for entry in entries:
        network = _network(entry)
        if network.prefixlen < 16:
            raise AppError('Refusing to open database access to ' + str(network) + '. Only specific backend '
                           'ranges are added, never 0.0.0.0/0.', 409, 'atlas_network')
        if network not in wanted:
            wanted.append(network)
    present = [_network(e) for e in access_entries()]
    missing = [n for n in wanted if not any(n.version == p.version and n.subnet_of(p) for p in present)]
    if missing:
        api('POST', '/groups/' + get_settings().atlas_project_id + '/accessList',
            [{'cidrBlock': str(n), 'comment': comment[:80]} for n in missing])
    return {'added': [str(n) for n in missing], 'present': [str(n) for n in wanted if n not in missing]}


def record(db, application_id):
    return db.application_databases.find_one({'_id': str(application_id)})


def public(row):
    """Safe to show a signed-in owner: never the password or the URI."""
    if not row:
        return None
    return {'database': row['database'], 'username': row['username'], 'cluster': row['cluster'],
            'status': row['status'], 'created_at': row.get('created_at'), 'rotated_at': row.get('rotated_at')}


def uri_of(db, application_id):
    """Decrypt the stored URI for server-side use only (deploy env vars)."""
    row = record(db, application_id)
    if not row or not row.get('uri'):
        raise AppError('This application has no provisioned database.', 409, 'atlas_configuration')
    return cipher().decrypt(row['uri'].encode()).decode()


def provision(db, application_id, indexes=()):
    """Idempotent: an existing healthy database is reused, never duplicated."""
    require()
    existing = record(db, application_id)
    if existing and existing.get('status') == 'ready':
        return public(existing)
    database, username = identifiers(application_id)
    secret = password()
    db.application_databases.update_one({'_id': str(application_id)}, {'$set': {
        'database': database, 'username': username, 'cluster': get_settings().atlas_cluster_name,
        'status': 'provisioning', 'created_at': (existing or {}).get('created_at') or now()}}, upsert=True)
    try:
        _upsert_user(username, secret, database)
        uri = connection_uri(username, secret, database)
        initialise(uri, database, indexes)
        db.application_databases.update_one({'_id': str(application_id)}, {'$set': {
            'uri': cipher().encrypt(uri.encode()).decode(), 'status': 'ready', 'rotated_at': now()}})
    except Exception as exc:
        db.application_databases.update_one({'_id': str(application_id)}, {'$set': {
            'status': 'failed', 'error': exc.message if isinstance(exc, AppError) else 'Provisioning failed.'}})
        raise
    return public(record(db, application_id))


def rotate(db, application_id):
    """New password for the same user and database. Redeploy to pick it up."""
    require()
    row = record(db, application_id)
    if not row:
        raise AppError('This application has no provisioned database.', 409, 'atlas_configuration')
    secret = password()
    _update_user(row['username'], secret, row['database'])
    uri = connection_uri(row['username'], secret, row['database'])
    initialise(uri, row['database'])
    db.application_databases.update_one({'_id': str(application_id)}, {'$set': {
        'uri': cipher().encrypt(uri.encode()).decode(), 'status': 'ready', 'rotated_at': now()}})
    return public(record(db, application_id))


def deprovision(db, application_id, drop_data=False):
    """Remove the user so the credential stops working; data removal is opt-in."""
    row = record(db, application_id)
    if not row:
        return
    require()
    api('DELETE', '/groups/' + get_settings().atlas_project_id + '/databaseUsers/admin/' + row['username'])
    if drop_data:
        try:
            client = MongoClient(get_settings().app_atlas_uri.strip(), serverSelectionTimeoutMS=15000)
            client.drop_database(row['database'])
            client.close()
        except PyMongoError:
            raise AppError('The database user was removed but its data could not be dropped.',
                           502, 'atlas_provider') from None
    db.application_databases.update_one({'_id': str(application_id)},
                                        {'$set': {'status': 'removed', 'removed_at': now()}, '$unset': {'uri': ''}})
