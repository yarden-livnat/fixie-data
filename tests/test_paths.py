"""Path tests"""
import os
import glob
import time
import subprocess
from collections.abc import Mapping

import pandas as pd

from fixie import json
from fixie import ENV

from fixie_data.paths import (resolve_pending_paths, listpaths, info, fetch,
    delete, table, gc)


SIMULATION = {
 'simulation': {
  'archetypes': {
   'spec': [
    {'lib': 'agents', 'name': 'Sink'},
    {'lib': 'agents', 'name': 'NullRegion'},
    {'lib': 'agents', 'name': 'NullInst'},
   ],
  },
  'control': {
   'duration': 2,
   'startmonth': 1,
   'startyear': 2000,
  },
  'facility': {
   'config': {'Sink': {'capacity': '1.00', 'in_commods': {'val': 'commodity'}}},
   'name': 'Sink',
  },
  'recipe': {
   'basis': 'mass',
   'name': 'commod_recipe',
   'nuclide': {'comp': '1', 'id': 'H1'},
  },
  'region': {
   'config': {'NullRegion': None},
   'institution': {
    'config': {'NullInst': None},
    'initialfacilitylist': {'entry': {'number': '1', 'prototype': 'Sink'}},
    'name': 'SingleInstitution',
   },
   'name': 'SingleRegion',
  },
 },
}


def _init_pending_paths(user):
    pptemp = ENV['FIXIE_PATHS_DIR'] + '/' + user + '-{0}-pending-path.json'
    pps = [{'user': user, 'holding': 'inf', 'path': '/hey'},
           {'user': user, 'holding': 42.0, 'path': '/there/is/it'},
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
    sims = ENV['FIXIE_SIMS_DIR']
    paths = {
        '/as': {'user': user, 'holding': 'inf', 'path': '/as',
                'created': time.time(), 'file': sims + '/0.txt',
                'jobid': 0},
        '/you': {'user': user, 'holding': 0.0, 'path': '/you',
                 'created': time.time(), 'file': sims + '/1.h5',
                 'jobid': 1},
        '/wish': {'user': user, 'holding': 42.0, 'path': '/wish',
                  'created': 1.0, 'file': sims + '/2.txt',
                  'jobid': 2},
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


def test_fetch_bytes(xdg, verify_user):
    user = 'rugen'
    given = _init_user_paths(user)
    fname = os.path.join(ENV['FIXIE_SIMS_DIR'], '0.txt')
    with open(fname, 'w') as f:
        f.write('as you wish')
    # fetch the file
    obs, status, msg = fetch('/as', user, '42', url=False, timeout=10.0)
    assert status, msg
    assert b'as you wish' == obs


def test_fetch_url(xdg, verify_user):
    user = 'vizzini'
    given = _init_user_paths(user)
    fname = os.path.join(ENV['FIXIE_SIMS_DIR'], '2.txt')
    with open(fname, 'w') as f:
        f.write('as I wish')
    # fetch the file
    obs, status, msg = fetch('/wish', user, '42', url=True, timeout=10.0)
    assert status, msg
    assert '/fetch?file=2.txt' == obs


def test_delete(xdg, verify_user):
    user = 'r.o.u.s'
    given = _init_user_paths(user)
    fname = os.path.join(ENV['FIXIE_SIMS_DIR'], '0.txt')
    with open(fname, 'w') as f:
        f.write('as you wish')
    # fetch the file
    status, msg = delete('/as', user, '42', timeout=10.0)
    assert status, msg
    assert not os.path.exists(fname)
    paths = resolve_pending_paths(user, timeout=10.0)
    assert '/as' not in paths


def test_table(xdg, verify_user):
    user = 'yellin'
    given = _init_user_paths(user)
    sim = json.dumps(SIMULATION)
    out = os.path.join(ENV['FIXIE_SIMS_DIR'], '1.h5')
    cmd = ['cyclus', '-o', out, '-f', 'json', sim]
    subprocess.check_call(cmd)
    # now get the table as a data frame
    tbl0, status, msg = table('Info', '/you', user, '42')
    assert status, msg
    assert isinstance(tbl0, pd.DataFrame)
    # now get the table as a python object (which also covers the JSON string case).
    tbl1, status, msg = table('Info', '/you', user, '42', format='json:dict')
    assert status, msg
    assert isinstance(tbl1, Mapping)


def test_gc(xdg, verify_user):
    user = 'valerie'
    given = _init_user_paths(user)
    for i in range(3):
        fname = os.path.join(ENV['FIXIE_SIMS_DIR'], str(i) + '.h5')
        with open(fname, 'w') as f:
            f.write('as you wish')
    # Garbage collection should remove only 1.h5, since it has a zero holding time
    status, msg = gc(timeout=10.0)
    assert status, msg
    obs = {ENV['FIXIE_SIMS_DIR'] + '/0.h5', ENV['FIXIE_SIMS_DIR'] + '/2.h5'}
    assert obs == set(glob.iglob(ENV['FIXIE_SIMS_DIR'] + '/*.h5'))
    paths = resolve_pending_paths(user, timeout=10.0)
    assert {'/as', '/wish'} == set(paths.keys())
