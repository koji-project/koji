import unittest

import koji

class TestTaskLabel(unittest.TestCase):
    def test_all(self):
        url = 'https+git://git.server/path/module#branch'
        module = '/path/module:branch'
        build = {'name': 'n', 'version': 'v', 'release': 'r', 'epoch': None}
        nvr = 'n-v-r'
        test_data = [
            ['randomdata', 'malformed task'],
            [{}, 'malformed task'],
            [None, 'malformed task'],
            [
                {'method': 'build', 'arch': 'x86_64',
                 'request': [url, 'target', 'opts'],
                }, 'build (target, %s)' % module
            ],
            [
                {'method': 'build', 'arch': 'x86_64',
                 'request': ['n-v-r.src.rpm', 'target', 'opts']
                }, 'build (target, n-v-r.src.rpm)'
            ],
            [
                {'method': 'maven', 'arch': 'x86_64',
                 'request': ['https+git://git.server/path/module#branch', 'target', 'opts'],
                }, 'maven (target, %s)' % module
            ],
            [
                {'method': 'maven', 'arch': 'x86_64',
                 'request': ['n-v-r.jar', 'target', 'opts'],
                }, 'maven (target, n-v-r.jar)'
            ],
            [
                {'method': 'indirectionimage', 'arch': 'x86_64',
                 'request': [build],
                }, 'indirectionimage (n, v, r)'
            ],
            [
                {'method': 'buildSRPMFromSCM', 'arch': 'x86_64',
                 'request': [url, 'build_tag', 'opts']
                }, 'buildSRPMFromSCM (%s)' % module
            ],
            [
                {'method': 'buildArch', 'arch': 'x86_64',
                 'request': ['pkg', 'root', 'arch', True, 'opts'],
                }, 'buildArch (pkg, arch)'
            ],
            [
                {'method': 'buildMaven', 'arch': 'x86_64',
                 'request': [url, {'name': 'build_tag', 'id': 123}, {}],
                }, 'buildMaven (build_tag)',
            ],
            [
                {'method': 'wrapperRPM', 'arch': 'x86_64',
                 'request': [url, {'name': 'target'}, build, 'task']
                }, 'wrapperRPM (target, n-v-r)',
            ],
            # winbuild, vmExec (not in legacy signatures)
            [
                {'method': 'buildNotification', 'arch': 'x86_64',
                 'request': ['rpts', build, 'target', 'weburl']
                }, 'buildNotification (n-v-r)'
            ],
            [
                {'method': 'newRepo', 'arch': 'x86_64',
                 'request': ['tag', 123, 'src']
                }, 'newRepo (tag)'
            ],
            [
                {'method': 'distRepo', 'arch': 'x86_64',
                 'request': ['tag', 123, 'keys', 'task_opts']
                }, 'distRepo (tag)'
            ],
            [
                {'method': 'tagBuild', 'arch': 'x86_64',
                 'request': ['tag', 123, True, 'from', True],
                }, 'tagBuild (x86_64)'
            ],
            [
                {'method': 'tagNotification', 'arch': 'x86_64',
                 'request': ['rcpts', True, 'tag', 'from', build, 'user'],
                }, 'tagNotification (x86_64)'
            ],
            [
                {'method': 'createrepo', 'arch': 'x86_64',
                 'request': ['repo_id', 'arch', 'oldrepo']
                }, 'createrepo (arch)'
            ],
            [
                {'method': 'createdistrepo', 'arch': 'x86_64',
                 'request': ['tag', 'repo_id', 'arch', 'keys', 'opts']
                }, 'createdistrepo (repo_id, arch)'
            ],
            [
                {'method': 'dependantTask', 'arch': 'x86_64',
                 'request': ['wait_list', [[1], [2]]],
                }, 'dependantTask (1, 2)'
            ],
            [
                {'method': 'chainbuild', 'arch': 'x86_64',
                 'request': ['srcs', 'target', 'opts'],
                }, 'chainbuild (target)'
            ],
            [
                {'method': 'chainmaven', 'arch': 'x86_64',
                 'request': ['srcs', 'target', 'opts'],
                }, 'chainmaven (target)'
            ],
            [
                {'method': 'waitrepo', 'arch': 'x86_64',
                 'request': ['tag', 'newer', ['nvr1', 'nvr2']]
                }, 'waitrepo (tag, nvr1, nvr2)'
            ],
            [
                {'method': 'appliance', 'arch': 'x86_64',
                 'request': ['name', 'version', 'arch', 'target', 'ksfile', 'opts'],
                }, 'appliance (arch, name-version, ksfile)',
            ],
            [
                {'method': 'livecd', 'arch': 'x86_64',
                 'request': ['name', 'version', 'arch', 'target', 'ksfile', 'opts'],
                }, 'livecd (arch, name-version, ksfile)',
            ],
            [
                {'method': 'image', 'arch': 'x86_64',
                 'request': ['name', 'version', 'arches', 'target', 'inst_tree', 'opts'],
                }, 'image (arches, name-version, inst_tree)',
            ],
            [
                {'method': 'livemedia', 'arch': 'x86_64',
                 'request': ['name', 'version', 'arches', 'target', 'ksfile', 'opts'],
                }, 'livemedia (arches, name-version, ksfile)',
            ],
            [
                {'method': 'createLiveCD', 'arch': 'x86_64',
                 'request': ['name', 'version', 'release', 'arch', {'name': 'target'}, 'build_tag',
                             'repo_info', 'ksfile', 'opts'],
                }, 'createLiveCD (target, name-version-release, ksfile, arch)',
            ],
            [
                {'method': 'restart', 'arch': 'noarch',
                 'request': [{'name': 'hostname'}],
                }, 'restart (hostname)'
            ],
            [
                {'method': 'restartVerify', 'arch': 'noarch',
                 'request': [123, {'name': 'hostname'}],
                }, 'restartVerify (hostname)'
            ],
            [
                {'method': 'vmExec', 'arch': 'x86_64',
                 'request': ['name', 'task_info', 'opts'],
                 }, 'vmExec (name)'
            ],
            [
                {'method': 'winbuild', 'arch': 'x86_64',
                 'request': ['name', 'source_url', 'target', 'opts'],
                 }, 'winbuild (target, :source_url)'
            ],

        ]

        for input, output in test_data:
            result = koji.taskLabel(input)
            self.assertEqual(result, output)
