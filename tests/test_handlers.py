"""Tests handlers object."""
import os
import time
import subprocess

import pytest
import tornado.web
from tornado.httpclient import HTTPError
from fixie import json
from fixie import ENV, fetch

from fixie_data.handlers import HANDLERS

from test_paths import _init_user_paths


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
APP = tornado.web.Application(HANDLERS)


@pytest.fixture
def app():
    return APP


def _write_simple_files(user):
    given = _init_user_paths(user)
    paths = ['/as', '/you', '/wish']
    for i, path in enumerate(paths):
        fname = given[path]['file']
        with open(fname, 'w') as f:
            f.write('as you wish ' + str(i))
    return given


@pytest.mark.gen_test
def test_listpaths_valid(xdg, verify_user, http_client, base_url):
    url = base_url + '/listpaths'
    body = {"user": "inigo", "token": "42"}
    exp = {'paths': [], 'status': True, 'message': 'Paths listed'}
    obs = yield fetch(url, body)
    assert exp == obs


@pytest.mark.gen_test
def test_info_valid(xdg, verify_user, http_client, base_url):
    url = base_url + '/info'
    body = {"user": "inigo", "token": "42"}
    exp = {'infos': [], 'status': True, 'message': 'Info found'}
    obs = yield fetch(url, body)
    assert exp == obs


@pytest.mark.gen_test
def test_fetch_valid(xdg, verify_user, http_client, base_url):
    user = "inigo"
    given = _write_simple_files(user)
    url = base_url + '/fetch'
    # test raw file fetching
    body = {"path": "/as", "user": user, "token": "42", 'url': False}
    obs = yield fetch(url, body)
    exp = {'file': b'as you wish 0', 'status': True, 'message': 'File fetched'}
    assert exp == obs
    # test url file fetching
    body = {"path": "/you", "user": user, "token": "42", 'url': True}
    obs = yield fetch(url, body)
    exp = {'file': '/fetch?file=1.h5', 'status': True, 'message': 'File fetched'}
    assert exp == obs
    # test getting the file via the url
    url += '?file=2.txt'
    response = yield http_client.fetch(url, method="GET")
    assert response.code == 200
    assert response.body == b'as you wish 2'


@pytest.mark.gen_test
def test_delete_valid(xdg, verify_user, http_client, base_url):
    user = "inigo"
    given = _write_simple_files(user)
    url = base_url + '/delete'
    # test deletion
    body = {"path": "/as", "user": user, "token": "42"}
    obs = yield fetch(url, body)
    exp = {'status': True, 'message': 'File removed'}
    assert exp == obs
    assert '0.txt' not in os.listdir(ENV['FIXIE_SIMS_DIR'])


@pytest.mark.gen_test
def test_table_valid(xdg, verify_user, http_client, base_url):
    user = "inigo"
    given = _init_user_paths(user)
    sim = json.dumps(SIMULATION)
    out = os.path.join(ENV['FIXIE_SIMS_DIR'], '1.h5')
    cmd = ['cyclus', '-o', out, '-f', 'json', sim]
    subprocess.check_call(cmd)
    url = base_url + '/table'
    # test deletion
    body = {"name": "Info", "path": "/you", "user": user, "token": "42"}
    obs = yield fetch(url, body)
    assert obs['status'], obs['message']
    assert obs['table']


@pytest.mark.gen_test
def test_gc_valid(xdg, verify_user, http_client, base_url):
    user = "inigo"
    given = _write_simple_files(user)
    url = base_url + '/gc'
    # test deletion
    body = {}
    obs = yield fetch(url, body)
    exp = {'status': True, 'message': ''}
    assert exp == obs
    assert '1.h5' not in os.listdir(ENV['FIXIE_SIMS_DIR'])
