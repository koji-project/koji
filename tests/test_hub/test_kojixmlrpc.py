import unittest

import kojixmlrpc


class TestHandler(unittest.TestCase):
    def test_list_api(self):
        basic_api = [
            {
                'name': '_listapi',
                'doc': 'List available API calls',
                'argspec': ([], None, None, None, [], None, {}),
                'argdesc': '()',
                'args': []
            },
            {
                'name': 'system.listMethods',
                'doc': None,
                'argspec': ([], None, None, None, [], None, {}),
                'argdesc': '()',
                'args': []
            },
            {
                'name': 'system.methodSignature',
                'doc': None,
                'argspec': (['method'], None, None, None, [], None, {}),
                'argdesc': '(method)',
                'args': ['method']},
            {
                'name': 'system.methodHelp',
                'doc': None,
                'argspec': (['method'], None, None, None, [], None, {}),
                'argdesc': '(method)', 'args': ['method']
            }
        ]
        h = kojixmlrpc.HandlerRegistry()
        result = h.list_api()
        self.assertEqual(result, basic_api)

    def test_list_methods(self):
        basic_methods = {
            '_listapi',
            'system.methodSignature',
            'system.listMethods',
            'system.methodHelp',
        }
        h = kojixmlrpc.HandlerRegistry()
        result = h.system_listMethods()
        self.assertEqual(set(result), basic_methods)

    def test_methodSignature(self):
        h = kojixmlrpc.HandlerRegistry()
        result = h.system_methodSignature('any method')
        self.assertEqual(result, 'signatures not supported')

    def test_methodHelp(self):
        help = '_listapi()\ndescription: List available API calls'
        h = kojixmlrpc.HandlerRegistry()
        result = h.system_methodHelp('_listapi')
        self.assertEqual(result, help)

    def _random_method(self, par1, par2, par3=None, par4='text'):
        """Random method docstring"""
        pass

    def test_registered_func(self):
        h = kojixmlrpc.HandlerRegistry()
        h.register_function(self._random_method, name='endpoint')

        result = h.system_listMethods()
        self.assertIn('endpoint', set(result))

        result = h.list_api()
        methods = {x['name']: x for x in result}
        self.assertIn('endpoint', methods.keys())

        api = methods['endpoint']
        self.assertEqual(api, {
            'name': 'endpoint',
            'doc': 'Random method docstring',
            'args': ['par1', 'par2', ['par3', None], ['par4', 'text']],
            'argdesc': "(par1, par2, par3=None, par4='text')",
            'argspec': (
                ['par1', 'par2', 'par3', 'par4'],
                None, None, (None, 'text'), [], None, {}
            ),
        })

        result = h.system_methodHelp('endpoint')
        help = "endpoint(par1, par2, par3=None, par4='text')\ndescription: Random method docstring"
        self.assertEqual(result, help)

