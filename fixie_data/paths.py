"""Manages paths for fixie data service."""
import os
import re
import glob
import fnmatch
import urllib.parse

from fixie import json
from fixie import ENV, flock, verify_user


_USER_PATH_FILE_TEMPLATE = '{0}/{1}.json'


def _user_path_file(user):
    """Helper function for making user path file"""
    return _USER_PATH_FILE_TEMPLATE.format(ENV['FIXIE_PATHS_DIR'], user)


def _load_user_paths(user, **kwargs):
    """Helper function for loading a user paths file."""
    if 'raise_errors' not in kwargs:
        kwargs['raise_errors'] = False
    user_path_file = _user_path_file(user)
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


def listpaths(user, token, pattern=None, **kwargs):
    """Lists paths for a user, matching a glob pattern if provided.

    Parameters
    ----------
    user : str
        Name of user to list paths for.
    token : str
        Token for a user.
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
    valid, msg, status = verify_user(user, token)
    if not status:
        return None, False, msg
    # load the user file
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


def info(user, token, paths=None, pattern=None, **kwargs):
    """Retrieves metadata information for paths.

    Parameters
    ----------
    user : str
        Name of user to list paths for.
    token : str
        Token for a user.
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
    if paths and pattern:
        return None, False, 'Only one of paths and patterns may be non-empty'
    valid, msg, status = verify_user(user, token)
    if not status:
        return None, False, msg
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


def _ensure_file(path, user, token, **kwargs):
    """Ensures that a path actually exist, returns the filename, the
    user paths, a status flag, and a message.
    """
    valid, msg, status = verify_user(user, token)
    if not valid or not status:
        return None, None, False, msg
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


def fetch(path, user, token, url=True, **kwargs):
    """Retrieves a path from the server.

    Parameters
    ----------
    path : str
        Path to retrieve.
    user : str
        Name of user to fetch a file for.
    token : str
        Token for a user.
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
    filename, userpaths, status, msg = _ensure_file(path, user, token, **kwargs)
    if not status:
        return None, False, msg
    fetcher = _fetch_url if url else _fetch_bytes
    url_or_file, msg = fetcher(filename)
    if url_or_file is None:
        return None, False, msg
    return url_or_file, True, 'File fetched'


def delete(path, user, token, **kwargs):
    """Removes a path (and its file) from the server.

    Parameters
    ----------
    path : str
        Path to remove.
    user : str
        Name of user to remove path for.
    token : str
        Token for a user.
    kwargs : other key words
        Passed into ``fixie.flock()`` when loading user paths file.

    Returns
    -------
    status : bool
        Whether the path can be fetched.
    message : str
        Status message, if needed.
    """
    filename, userpaths, status, msg = _ensure_file(path, user, token, **kwargs)
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

