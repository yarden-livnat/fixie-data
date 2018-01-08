"""Tornado handlers for interfacing with fixie data management."""
import os

from fixie import ENV, RequestHandler

from fixie_data.paths import listpaths, info, fetch, delete, table


class ListPaths(RequestHandler):

    schema = {'user': {'type': 'string', 'empty': False, 'required': True},
              'token': {'type': 'string', 'regex': '[0-9a-fA-F]+', 'required': True},
              'pattern': {'type': 'string', 'nullable': True},
              }
    response_keys = ('paths', 'status', 'message')

    def post(self):
        resp = listpaths(**self.request.arguments)
        response = dict(zip(self.response_keys, resp))
        self.write(response)


class Info(RequestHandler):

    schema = {'user': {'type': 'string', 'empty': False, 'required': True},
              'token': {'type': 'string', 'regex': '[0-9a-fA-F]+', 'required': True},
              'paths': {'anyof': [
                {'type': 'string'},
                {'type': 'list', 'empty': False,
                 'schema': {'type': 'string', 'empty': False}},
                ], 'nullable': True, 'excludes': 'pattern'},
              'pattern': {'type': 'string', 'nullable': True, 'excludes': 'paths'},
              }
    response_keys = ('infos', 'status', 'message')

    def post(self):
        resp = info(**self.request.arguments)
        response = dict(zip(self.response_keys, resp))
        self.write(response)


class Fetch(RequestHandler):

    schema = {'user': {'type': 'string', 'empty': False, 'required': True},
              'token': {'type': 'string', 'regex': '[0-9a-fA-F]+', 'required': True},
              'path': {'type': 'string', 'empty': False, 'required': True},
              'url': {'type': 'boolean'},
              }
    response_keys = ('file', 'status', 'message')
    chunksize = 16384  # 16 Kb

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

    def post(self, *args, **kwargs):
        resp = fetch(**self.request.arguments)
        response = dict(zip(self.response_keys, resp))
        self.write(response)


class Delete(RequestHandler):

    schema = {'user': {'type': 'string', 'empty': False, 'required': True},
              'token': {'type': 'string', 'regex': '[0-9a-fA-F]+', 'required': True},
              'path': {'type': 'string', 'empty': False, 'required': True},
              }
    response_keys = ('status', 'message')

    def post(self, *args, **kwargs):
        resp = delete(**self.request.arguments)
        response = dict(zip(self.response_keys, resp))
        self.write(response)


class Table(RequestHandler):

    schema = {'name': {'type': 'string', 'empty': False, 'required': True},
              'path': {'type': 'string', 'empty': False, 'required': True},
              'user': {'type': 'string', 'empty': False, 'required': True},
              'token': {'type': 'string', 'regex': '[0-9a-fA-F]+', 'required': True},
              'conds': {'type': 'list',
                        'schema': {'type': 'list', 'empty': False,
                                   'minlength': 3, 'maxlength': 3},
                        'nullable': True},
              'format': {'type': 'string', 'allowed': ['json', 'json:str', 'json:dict']},
              'orient': {'type': 'string', 'allowed': ['split', 'records', 'index',
                                                       'columns', 'values']},
              }
    response_keys = ('table', 'status', 'message')

    def post(self, *args, **kwargs):
        args = self.request.arguments
        if 'format' not in args:
            args['format'] = 'json:dict'
        resp = table(**args)
        response = dict(zip(self.response_keys, resp))
        self.write(response)


HANDLERS = [
    ('/listpaths', ListPaths),
    ('/info', Info),
    ('/fetch', Fetch),
    ('/delete', Delete),
    ('/table', Table),
]
