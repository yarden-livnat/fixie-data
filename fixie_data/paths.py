"""Manages paths for fixie data service."""
import os
import re
import glob
import time
import fnmatch
import urllib.parse

from lazyasd import lazyobject

from fixie import json
from fixie import ENV, flock


_USER_PATH_FILE_TEMPLATE = '{0}/{1}.json'


@lazyobject
def cyclus_lib():
    from cyclus import lib
    return lib


def _user_path_file(user):
    """Helper function for making user path file"""
    return _USER_PATH_FILE_TEMPLATE.format(ENV['FIXIE_PATHS_DIR'], user)


def _load_user_paths(user_or_file, is_user=True,  **kwargs):
    """Helper function for loading a user paths file."""
    if 'raise_errors' not in kwargs:
        kwargs['raise_errors'] = False
    user_path_file = _user_path_file(user_or_file) if is_user else user_or_file
    with flock(user_path_file, **kwargs) as lockfd:
        if lockfd == 0:
            return
        elif os.path.exists(user_path_file):
            with open(user_path_file) as f:
                paths = json.load(f)
            for info in paths.values():
                info['holding'] = float(info.get('holding', 'inf'))
            return paths
        else:
            return {}


def _dump_user_paths(user, paths, **kwargs):
    """Helper function for dumping a user paths file. Returns whether or
    not the dump occured successfully.
    """
    if 'raise_errors' not in kwargs:
        kwargs['raise_errors'] = False
    user_path_file = _user_path_file(user)
    with flock(user_path_file, **kwargs) as lockfd:
        if lockfd == 0:
            if kwargs['raise_errors']:
                raise RuntimeError('Could not dump user paths file for ' + user)
            else:
                return False
        with open(user_path_file, 'w') as f:
            json.dump(paths, f, indent=1)
    return True


def resolve_pending_paths(user, **kwargs):
    """This function searches for any pending path files for a user and then adds
    their information into the users path file (``$FIXIE_PATHS_DIR/user.json``).
    This will return the contents of the paths file
    after the update. Pending path files must be names to match the glob:
    ``$FIXIE_PATHS_DIR/username*-pending-path.json``. Additional keyword arguments
    are passed into ``fixie.flock()``. Returns None if the user paths file could
    not be loaded.
    """
    pattern = '{0}/{1}*-pending-path.json'.format(ENV['FIXIE_PATHS_DIR'], user)
    files = glob.glob(pattern)
    if len(files) == 0:
        return _load_user_paths(user, **kwargs)
    # actually have pending files, lets read them in, update them, add them to the
    # existing the paths file, and then delete the pending files.
    new_paths = {}
    for fname in files:
        with open(fname) as f:
            new_path = json.load(f)
        # need to add created time of file
        new_path['holding'] = float(new_path['holding'])
        new_path['created'] = os.stat(new_path['file']).st_ctime
        new_paths[new_path['path']] = new_path
    paths = _load_user_paths(user, **kwargs)
    if paths is None:
        return None
    paths.update(new_paths)
    _dump_user_paths(user, paths, **kwargs)
    for fname in files:
        os.remove(fname)
    return paths


# def listpaths(user, token, pattern=None, **kwargs):
def listpaths(user, pattern=None, **kwargs):

    """Lists paths for a user, matching a glob pattern if provided.

    Parameters
    ----------
    user : str
        Name of user to list paths for.
    pattern : str or None, optional
        Glob string to match paths. If None or an empty string, all
        paths are returned.
    kwargs : other key words
        Passed into ``fixie.flock()`` when loading user paths file.

    Returns
    -------
    paths : list of str or None
        Path names that matched the given pattern. None if status is False.
    status : bool
        Whether the paths were correctly found.
    message : str
        Status message, if needed.
    """

    infos = resolve_pending_paths(user, **kwargs)
    if infos is None:
        return None, False, 'User paths file could not be loaded.'
    # filter the paths
    paths = sorted(infos.keys())
    if pattern:
        try:
            r = re.compile(fnmatch.translate(pattern))
        except Exception:
            return None, False, 'Could not compile path pattern'
        paths = [p for p in paths if r.match(p) is not None]
    return paths, True, 'Paths listed'


def _pathkey(x):
    return x['path']


def info(user, paths=None, pattern=None, **kwargs):
    """Retrieves metadata information for paths.

    Parameters
    ----------
    user : str
        Name of user to list paths for.
    paths : str or list of str or None, optional
        Only return info for specific paths. If non-empty, pattern must be empty.
    pattern : str or None, optional
        Glob string to match paths. If None or an empty string, all
        paths are returned. If non-empty, paths must be empty.
    kwargs : other key words
        Passed into ``fixie.flock()`` when loading user paths file.

    Returns
    -------
    infos : list of dicts or None
        Path infomation dicts. None if status is False.
    status : bool
        Whether the paths were correctly found.
    message : str
        Status message, if needed.
    """
    # if paths and pattern:
    #     return None, False, 'Only one of paths and patterns may be non-empty'

    # load the user file
    userpaths = resolve_pending_paths(user, **kwargs)
    if userpaths is None:
        return None, False, 'User paths file could not be loaded.'
    # filter paths and convert to list
    if paths:
        if isinstance(paths, str):
            paths = [paths]
        infos = [userpaths[path] for path in paths if path in userpaths]
    elif pattern:
        try:
            r = re.compile(fnmatch.translate(pattern))
        except Exception:
            return None, False, 'Could not compile path pattern'
        infos = [v for k, v in userpaths.items() if r.match(k) is not None]
        infos.sort(key=_pathkey)
    else:
        infos = list(userpaths.values())
        infos.sort(key=_pathkey)
    return infos, True, 'Info found'


def _fetch_url(filename):
    # first, get the pathname relative to the simulation dir
    relname = os.path.relpath(filename, ENV['FIXIE_SIMS_DIR'])
    url = '/fetch?' + urllib.parse.urlencode({'file': relname})
    return url, ''


def _fetch_bytes(filename):
    try:
        with open(filename, 'rb') as f:
            b = f.read()
        msg = ''
    except Exception as e:
        b = None
        msg = str(e) + '\n\nFailed to read file: ' + filename
    return b, msg


def _ensure_file(path, user, **kwargs):
    """Ensures that a path actually exist, returns the filename, the
    user paths, a status flag, and a message.
    """
    # valid, msg, status = verify_user(user, token)
    # if not valid or not status:
    #     return None, None, False, msg
    # load the user file
    userpaths = resolve_pending_paths(user, **kwargs)
    if userpaths is None:
        return None, None, False, 'User paths file could not be loaded.'
    # get the file
    info = userpaths.get(path, None)
    if info is None:
        return None, None, False, 'Path {0!r} does not exist'.format(path)
    filename = info.get('file', None)
    if not filename:
        return None, None, False, 'Path {0!r} does not not have a file'.format(path)
    if not os.path.isfile(filename):
        msg = 'Path file {0!r} does not exist or is a directory'.format(filename)
        return None, None, False, msg
    return filename, userpaths, True, ''


def fetch(user, path, url=False, **kwargs):
    """Retrieves a path from the server.

    Parameters
    ----------
    user : str
        Name of user to fetch a file for.
    path : str
        Path to retrieve.

    url : boolean, optional
        Whether to return a URL from which the file can be downloaded, or
        the bytes of the file itself.
    kwargs : other key words
        Passed into ``fixie.flock()`` when loading user paths file.

    Returns
    -------
    url_or_file : str, bytes, or None
        URL (relative to the server base) where the file may be downloaded (via GET),
        or the bytes of the file, or None if the status is False/
    status : bool
        Whether the path can be fetched.
    message : str
        Status message, if needed.
    """
    filename, userpaths, status, msg = _ensure_file(path, user, **kwargs)
    if not status:
        return None, False, msg
    fetcher = _fetch_url if url else _fetch_bytes
    url_or_file, msg = fetcher(filename)
    if url_or_file is None:
        return None, False, msg
    return url_or_file, True, 'File fetched'


def delete(user, path, **kwargs):
    """Removes a path (and its file) from the server.

    Parameters
    ----------
    path : str
        Path to remove.
    user : str
        Name of user to remove path for.
    kwargs : other key words
        Passed into ``fixie.flock()`` when loading user paths file.

    Returns
    -------
    status : bool
        Whether the path can be fetched.
    message : str
        Status message, if needed.
    """
    filename, userpaths, status, msg = _ensure_file(path, user,  **kwargs)
    if not status:
        return False, msg
    # actually try to remove the file
    try:
        os.remove(filename)
    except Exception as e:
        return False, str(e) + '\n\n' + 'Could not remove path ' + path
    del userpaths[path]
    status = _dump_user_paths(user, userpaths, **kwargs)
    if not status:
        msg = ('Removed file {0!r} but could not remove path entry {1!r}, '
               'system is in inconsistent state.')
        return False, msg.format(filename, path)
    return True, 'File removed'


def _open_db(filename):
    """Opens a Cyclus databse."""
    db = None
    msg = ''
    _, ext = os.path.splitext(filename)
    if ext == '.h5':
        try:
            db = cyclus_lib.Hdf5Back(filename)
        except Exception as e:
            msg = str(e) + '\n\nCould not open database as HDF5 file.'
    elif ext == '.sqlite':
        try:
            db = cyclus_lib.SqliteBack(filename)
        except Exception as e:
            msg = str(e) + '\n\nCould not open database as SQLite file.'
    else:
        msg = 'extension not recongnized as Cyclus output file.'
    return db, msg


def table(user, name, path, conds=None, format='dataframe', orient='columns',
          **kwargs):
    """Retrieves a table from a path (which must represent a Cyclus database).

    Parameters
    ----------
    user : str
        Name of user to remove path for.
    name : str
        Name of table to retrieve.
    path : str
        Path to remove.
    conds : list of 3-tuples or None, optional
        Conditions to filter table rows with. See the Cyclus FullBackend for
        more information.  The default (None) is to provide the complete
        table.
    format : str, optional
        Flag for type of object to return. If "dataframe" (default), a pandas
        DataFrame will be returned. If "json:dict", a Python dict that
        is JSON serializable (via ``fixie.json``) will be returned. If "json" or
        "json:str" a JSON string will be returned.
    orient : str, optional
        Flag for orientation that is passed into ``pandas.DataFrame.to_json()``
        See this method for more documentation.
    kwargs : other key words
        Passed into ``fixie.flock()`` when loading user paths file.

    Returns
    -------
    table : pandas.DataFrame or dict str or None
        The contents of the table, structure depends on format and orient
        kwargs. None if table could not be loaded
    status : bool
        Whether the table could be loaded.
    message : str
        Status message, if needed.
    """
    filename, userpaths, status, msg = _ensure_file(path, user, **kwargs)
    if not status:
        return None, False, msg
    db, msg = _open_db(filename)
    if db is None:
        return None, False, msg
    try:
        with db:
            tbl = db.query(name, conds=conds)
    except Exception as e:
        return None, False, str(e) + '\n\nTable could not be loaded from database'
    # now that we have the table, format it.
    if format == 'dataframe':
        rtn = tbl
    elif format.startswith('json'):
        try:
            rtn = tbl.to_json(orient=orient, default_handler=json.default)
        except Exception as e:
            return None, False, str(e) + '\n\nCould not format table'
        if format == "json:dict":
            rtn = json.loads(rtn)
    else:
        return None, False, 'Table format {0!r} not valid'.format(format)
    return rtn, True, 'Table read'


def gc(**kwargs):
    """Cleans up paths & files that have past their holding time.

    Parameters
    ----------
    kwargs : other key words
        Passed into ``fixie.flock()`` when loading user paths file.

    Returns
    -------
    status : bool
        Whether garbage collection completed.
    message : str
        Status message, if needed.
    """
    if 'raise_errors' not in kwargs:
        kwargs['raise_errors'] = False
    msg = ''
    now = time.time()
    pattern = ENV['FIXIE_PATHS_DIR'] + '/*.json'
    for user_path_file in glob.iglob(pattern):
        if user_path_file.endswith('-pending-path.json'):
            continue
        with flock(user_path_file, **kwargs) as lockfd:
            # need to keep file locked for whole gc process
            if lockfd == 0:
                msg += user_path_file + ' could not be loaded\n\n'
                continue
            with open(user_path_file) as f:
                paths = json.load(f)
            # delete files
            paths_to_del = set()
            for path, info in paths.items():
                age = now - info['created']
                holding = float(info.get('holding', 'inf'))
                fname = info['file']
                if age >= holding and os.path.isfile(fname):
                    try:
                        os.remove(fname)
                    except Exception as e:
                        msg += str(e) + '\nCould not delete file ' + fname + '\n\n'
                        continue
                    paths_to_del.add(path)
            # delete paths
            if len(paths_to_del) == 0:
                continue
            for path in paths_to_del:
                del paths[path]
            with open(user_path_file, 'w') as f:
                json.dump(paths, f, indent=1)
    return not msg, msg
