import mock
import os
import datetime
import unittest

from kojihub import _write_maven_repo_metadata

class TestWriteMavenRepoMetadata(unittest.TestCase):

    # Show long diffs in error output...
    maxDiff = None

    @mock.patch('kojihub._generate_maven_metadata')
    def test_write_maven_repo_metadata(self, gendata_mock):
        destdir = '/tmp'
        artifacts = set()

        # group_id, artifact_id, version
        artifacts.add(('0', '1', '1.2'))
        artifacts.add(('0', '1', '1.3'))
        artifacts.add(('0', '1', '1.1'))
        artifacts.add(('0', '1', '1.3.1'))
        artifacts.add(('0', '1', '1.3.15'))
        artifacts.add(('0', '1', '1.3.3'))
        artifacts.add(('0', '1', '1.3.6'))
        artifacts.add(('0', '1', '1.3.11'))

        now = datetime.datetime.now()
        with mock.patch('kojihub.open', create=True) as openf_mock:
            with mock.patch('datetime.datetime') as datetime_mock:
                datetime_mock.now.return_value = now
                _write_maven_repo_metadata(destdir, artifacts)

        openf_mock.assert_called_with(
            os.path.join(destdir, 'maven-metadata.xml'), 'w')

        handle = openf_mock().__enter__()
        expected = """\
<?xml version="1.0"?>
<metadata>
  <groupId>0</groupId>
  <artifactId>1</artifactId>
  <versioning>
    <latest>1.3.15</latest>
    <release>1.3.15</release>
    <versions>
      <version>1.1</version>
      <version>1.2</version>
      <version>1.3</version>
      <version>1.3.1</version>
      <version>1.3.3</version>
      <version>1.3.6</version>
      <version>1.3.11</version>
      <version>1.3.15</version>
    </versions>
    <lastUpdated>%s</lastUpdated>
  </versioning>
</metadata>
""" % now.strftime('%Y%m%d%H%M%S')
        handle.write.assert_called_with(expected)
