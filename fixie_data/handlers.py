"""Tornado handlers for interfacing with fixie data management."""
import os

from fixie import ENV, RequestHandler
from fixie_data.paths import listpaths, info, fetch, delete, table, gc
import fixie_creds


class ListPaths(RequestHandler):

    schema = {'pattern': {'type': 'string', 'nullable': True}, }
    response_keys = ('paths', 'status', 'message')

    @fixie_creds.authenticated
    def post(self):
        resp = listpaths(self.get_current_user(), **self.request.arguments)
        response = dict(zip(self.response_keys, resp))
        self.write(response)


class Info(RequestHandler):

    schema = {'paths': {'anyof': [
                {'type': 'string'},
                {'type': 'list', 'empty': False,
                 'schema': {'type': 'string', 'empty': False}},
                ], 'nullable': True, 'excludes': 'pattern'},
              'pattern': {'type': 'string', 'nullable': True, 'excludes': 'paths'},
              }
    response_keys = ('infos', 'status', 'message')

    @fixie_creds.authenticated
    def post(self):
        resp = info(self.get_current_user(), **self.request.arguments)
        response = dict(zip(self.response_keys, resp))
        self.write(response)


class Fetch(RequestHandler):

    schema = {'path': {'type': 'string', 'empty': False, 'required': True},
              'url': {'type': 'boolean'},
              }
    response_keys = ('file', 'status', 'message')
    chunksize = 16384  # 16 Kb

    @fixie_creds.authenticated
    def get(self, *args, **kwargs):
        """Actually get a file"""
        files = self.request.arguments['file']
        if len(files) != 1:
            self.send_error(400, message='Exactly one file may be fetched!')
            return
        fname = files[0]
        if isinstance(fname, bytes):
            fname = fname.decode('utf-8')
        fname = os.path.join(ENV['FIXIE_SIMS_DIR'], fname)
        if not os.path.isfile(fname):
            self.send_error(400, message='File not found')
            return
        with open(fname, 'rb') as f:
            while True:
                b = f.read(self.chunksize)
                if not b:
                    break
                self.write(b)
        self.finish()

    @fixie_creds.authenticated
    def post(self, *args, **kwargs):
        resp = fetch(self.get_current_user(), **self.request.arguments)
        response = dict(zip(self.response_keys, resp))
        self.write(response)


class Delete(RequestHandler):

    schema = {'path': {'type': 'string', 'empty': False, 'required': True} }
    response_keys = ('status', 'message')

    @fixie_creds.authenticated
    def post(self, *args, **kwargs):
        resp = delete(self.get_current_user(), **self.request.arguments)
        response = dict(zip(self.response_keys, resp))
        self.write(response)


class Table(RequestHandler):

    schema = {'name': {'type': 'string', 'empty': False, 'required': True},
              'path': {'type': 'string', 'empty': False, 'required': True},
              'conds': {'type': 'list',
                        'schema': {'type': 'list', 'empty': False,
                                   'minlength': 3, 'maxlength': 3},
                        'nullable': True},
              'format': {'type': 'string', 'allowed': ['json', 'json:str', 'json:dict']},
              'orient': {'type': 'string', 'allowed': ['split', 'records', 'index',
                                                       'columns', 'values']},
              }
    response_keys = ('table', 'status', 'message')

    @fixie_creds.authenticated
    def post(self, *args, **kwargs):
        args = self.request.arguments
        if 'format' not in args:
            args['format'] = 'json:dict'
        resp = table(self.get_current_user(), **args)
        response = dict(zip(self.response_keys, resp))
        self.write(response)


class GC(RequestHandler):

    schema = {}
    response_keys = ('status', 'message')

    def post(self, *args, **kwargs):
        resp = gc(**self.request.arguments)
        response = dict(zip(self.response_keys, resp))
        self.write(response)


HANDLERS = [
    ('/listpaths', ListPaths),
    ('/info', Info),
    ('/fetch', Fetch),
    ('/delete', Delete),
    ('/table', Table),
    ('/gc', GC),
]
