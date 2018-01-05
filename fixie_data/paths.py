"""Manages paths for fixie data service."""
import os
import glob

from fixie import json
from fixie import ENV, flock


def _load_user_paths(user, **kwargs):
    """Helper function for loading a user paths file."""
    user_path_file = ENV['FIXIE_PATHS_DIR'] + '/' + user + '.json'
    with flock(user_path_file, **kwargs) as lockfd:
        if lockfd == 0:
            return
        elif os.path.exists(user_path_file):
            with open(user_path_file) as f:
                paths = json.load(f)
            return paths
        else:
            return {}


def _dump_user_paths(user, **kwargs):
    """Helper function for dumping a user paths file."""


def resolve_pending_paths(user, return_paths=False, **kwargs):
    """This function searches for any pending path files for a user and then adds
    their information into the users path file (``$FIXIE_PATHS_DIR/user.json``).
    This will return the contents of the paths file
    after the update. Pending path files must be names to match the glob:
    ``$FIXIE_PATHS_DIR/username*-pending-path.json``. Additional keyword arguments
    are passed into ``fixie.flock()``
    """
    pathsdir = ENV['FIXIE_PATHS_DIR']
    pattern = '{0}/{1}*-pending-path.json'.format(pathsdir, user)
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
        new_path['created'] = os.stat(new_path['file']).st_ctime
        new_paths[new_path['path']] = new_path
    paths = _load_user_paths(user, **kwargs)
    paths.update(new_paths)