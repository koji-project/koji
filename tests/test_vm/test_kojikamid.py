import base64
import filecmp
import importlib.machinery
import importlib.util
import os
import tempfile
from subprocess import check_call

VM_TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
LOGO_FIXTURE = os.path.join(VM_TESTS_DIR, 'data', 'koji.png')
TESTS_DIR = os.path.dirname(VM_TESTS_DIR)
VM_DIR = os.path.join(os.path.dirname(TESTS_DIR), 'vm')

# Generate the kojikamid file before importing.
tmpfile = tempfile.NamedTemporaryFile(prefix='kojikamid.')
check_call(['bash', 'fix_kojikamid.sh'], cwd=VM_DIR, stdout=tmpfile)
print(tmpfile.name)

# Dynamically import our temporary kojikamid file.
loader = importlib.machinery.SourceFileLoader('kojikamid', tmpfile.name)
spec = importlib.util.spec_from_loader(loader.name, loader)
kojikamid = importlib.util.module_from_spec(spec)
loader.exec_module(kojikamid)


class FakeServer(object):
    def getTaskInfo(self):
        # Koji's getTaskInfo(..., request=True) returns the task's request
        # data. kojivmd strips this down to the second element of that request
        # and returns it here:
        return ['git://example.com/ceph.git#abc123',
                'ceph-6.1-win-build',
                {'repo_id': 2,
                 'winspec': 'git://example.com/pkg.git?ceph#def456'}]

    def getFile(self, buildinfo, archiveinfo, offset, length, type):
        # Return a base64-encoded static fixture (a PNG image).
        offset = int(offset)
        length = int(length)
        with open(LOGO_FIXTURE, 'rb') as fileobj:
            try:
                fileobj.seek(offset)
                data = fileobj.read(length)
                encoded = base64.b64encode(data).decode()
                del data
                return encoded
            finally:
                fileobj.close()


def test_fetch_file(tmpdir):
    server = FakeServer()
    build = kojikamid.WindowsBuild(server)
    basedir = str(tmpdir)
    buildinfo = {
        'name': 'wnbd',
    }
    fileinfo = {
        'localpath': 'koji.png',
        'checksum_type': 2,  # sha256
        'checksum': 'f78bc62287eec7641a85a7d1c0435c995672e7f46e33de72a82775b1fb16a93f',
    }
    build.fetchFile(basedir, buildinfo, fileinfo, 'win')
    fetched = str(tmpdir.join('koji.png'))
    assert filecmp.cmp(fetched, LOGO_FIXTURE)
