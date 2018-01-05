"""Path tests"""
import os
import time

from fixie import json
from fixie import ENV

from fixie_data.paths import resolve_pending_paths, listpaths, info


def _init_pending_paths(user):
    pptemp = ENV['FIXIE_PATHS_DIR'] + '/' + user + '-{0}-pending-path.json'
    pps = [{'user': user, 'holding': 'inf', 'path': '/hey'},
           {'user': user, 'holding': 42.5, 'path': '/there/is/it'},
           {'user': user, 'holding': '1e300', 'path': '/me/you/are-looking-for'},
           ]
    for i, pp in enumerate(pps):
        pp['jobid'] = i
        fname = pp['file'] = pptemp.format(i)
        with open(fname, 'w') as f:
            json.dump(pp, f, indent=1)
    return pps


def _user_path_file(user):
    return ENV['FIXIE_PATHS_DIR'] + '/' + user + '.json'


def _init_user_paths(user):
    upf = _user_path_file(user)
    paths = {
        '/as': {'user': user, 'holding': 'inf', 'path': '/as',
                'created': time.time()},
        '/you': {'user': user, 'holding': 10.0, 'path': '/you',
                 'created': time.time()},
        '/wish': {'user': user, 'holding': 42.0, 'path': '/wish',
                  'created': 1.0},
        }
    with open(upf, 'w') as f:
        json.dump(paths, f, indent=1)
    return paths


def test_resolve_pending_paths_no_files(xdg):
    obs = resolve_pending_paths('inigo')
    assert {} == obs


def test_resolve_pending_paths_no_user_file(xdg):
    # set up system
    user = 'buttercup'
    pps = _init_pending_paths(user)
    for pp in pps:
        assert os.path.exists(pp['file'])
    upf = _user_path_file(user)
    assert not os.path.exists(upf)
    # resolve the pending paths we just created.
    paths = resolve_pending_paths(user)
    # make sure that the paths file exists and the pending paths are gone.
    for pp in pps:
        assert not os.path.exists(pp['file'])
    assert os.path.exists(upf)
    # make sure the paths are well formed
    for path, info in paths.items():
        assert user == info['user']
        assert path == info['path']
        assert 'created' in info
        assert isinstance(info['holding'], float)


def test_resolve_pending_paths_no_pending_paths(xdg):
    # set up system
    user = 'fezzik'
    given = _init_user_paths(user)
    upf = _user_path_file(user)
    assert os.path.exists(upf)
    # no pending paths to resolve, but let's make sure we get the user paths.
    paths = resolve_pending_paths(user)
    for path, info in paths.items():
        assert path in given
        assert isinstance(info['holding'], float)


def test_resolve_pending_paths_all(xdg):
    # set up system
    user = 'miracle-max'
    given = _init_user_paths(user)
    pps = _init_pending_paths(user)
    upf = _user_path_file(user)
    assert os.path.exists(upf)
    for pp in pps:
        assert os.path.exists(pp['file'])
    # resolve the pending paths we just created.
    paths = resolve_pending_paths(user)
    # make sure that the paths file exists and the pending paths are gone.
    for pp in pps:
        assert not os.path.exists(pp['file'])
    assert os.path.exists(upf)
    # make sure that all keys are present in the paths
    exp_paths = {pp['path'] for pp in pps}
    exp_paths.update(given.keys())
    obs_paths = set(paths.keys())
    assert exp_paths == obs_paths


def test_listpaths(xdg, verify_user):
    user = 'westley'
    given = _init_user_paths(user)
    # no pattern
    exp = ['/as', '/wish', '/you']
    paths, status, msg = listpaths(user, '42', timeout=10.0)
    assert exp == paths
    # s-pattern
    exp = ['/as', '/wish']
    paths, status, msg = listpaths(user, '42', '*s*', timeout=10.0)
    assert exp == paths


def test_info(xdg, verify_user):
    user = 'humperdinck'
    given = _init_user_paths(user)
    # no pattern, no path
    exp = []
    for p, i in sorted(given.items()):
        i['holding'] = float(i['holding'])
        exp.append(i)
    infos, status, msg = info(user, '42', timeout=10.0)
    assert status
    assert exp == infos
    # s-pattern, no paths
    infos, status, msg = info(user, '42', pattern='*s*', timeout=10.0)
    assert status
    assert exp[:2] == infos
    # no pattern, single path
    infos, status, msg = info(user, '42', paths='/you', timeout=10.0)
    assert status
    assert exp[-1:] == infos
    # no pattern, paths
    infos, status, msg = info(user, '42', paths=['/you', 'non-exist', '/wish'],
                              timeout=10.0)
    assert status
    assert exp[-2:][::-1] == infos
    # pattern and paths
    infos, status, msg = info(user, '42', pattern='*s*', paths='/you', timeout=10.0)
    assert not status
    assert infos is None

