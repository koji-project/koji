import unittest

from kojiweb.util import formatMode, formatLink, escapeHTML

class TestFormatMode(unittest.TestCase):
    def test_format_mode(self):
        formats = (
            ('drwxrwxr-x', 0x41fd), # dir
            ('-rw-------', 0x8180), # reg. file
            ('crw--w----', 0x2190), # /dev/tty0
            ('brw-rw----', 0x61b0), # /dev/sda
            ('lrwxrwxrwx', 0xa1ff), # symlink
            ('srwxr-xr-x', 0xc1ed), # socket
            ('-rwsrwsr--', 0x8db4), # suid
        )

        for s, mode in formats:
            self.assertEqual(formatMode(mode), s)

    def test_format_link(self):
        formats = (
            ('test me', 'test me'),
            ('  test ', 'test'),
            ('<script>hack</script>', '&lt;script&gt;hack&lt;/script&gt;'),
            ('not://valid', 'not://valid'),
            ('https://foo.com', '<a href="https://foo.com">https://foo.com</a>'),
            ('http://bar.com/', '<a href="http://bar.com/">http://bar.com/</a>'),
            ('HTtP://BaR.CoM/', '<a href="HTtP://BaR.CoM/">HTtP://BaR.CoM/</a>'),
            ('https://baz.com/baz&t=1', '<a href="https://baz.com/baz&amp;t=1">https://baz.com/baz&amp;t=1</a>'),
            ('ssh://git@pagure.io/foo', '<a href="ssh://git@pagure.io/foo">ssh://git@pagure.io/foo</a>'),
            ('git://git@pagure.io/foo', '<a href="git://git@pagure.io/foo">git://git@pagure.io/foo</a>'),
            ('obs://build.opensuse.org/foo', '<a href="obs://build.opensuse.org/foo">obs://build.opensuse.org/foo</a>'),
        )

        for input, output in formats:
            self.assertEqual(formatLink(input), output)

    def test_escape_html(self):
        tests = (
            ('test me', 'test me'),
            ('test <danger>', 'test &lt;danger&gt;'),
            ('test <danger="true">', 'test &lt;danger=&quot;true&quot;&gt;'),
            ("test <danger='true'>", 'test &lt;danger=&#x27;true&#x27;&gt;'),
            ('test&test', 'test&amp;test'),
            ('test&amp;test', 'test&amp;test'),
        )

        for input, output in tests:
            self.assertEqual(escapeHTML(input), output)
