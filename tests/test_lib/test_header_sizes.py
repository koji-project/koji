# coding=utf-8
from __future__ import absolute_import
import os.path
import unittest

import koji
import rpm


SIGTAG_SIZE = 1000
try:
    SIGTAG_LONGSIZE = rpm.RPMTAG_LONGSIGSIZE
except NameError:
    SIGTAG_LONGSIZE = None


class TestHeaderSizes(unittest.TestCase):

    RPMFILES = [
        "test-deps-1-1.fc24.x86_64.rpm",
        "test-files-1-1.fc27.noarch.rpm",
        "test-nosrc-1-1.fc24.nosrc.rpm",
        "test-deps-1-1.fc24.x86_64.rpm.signed",
        "test-nopatch-1-1.fc24.nosrc.rpm",
        "test-src-1-1.fc24.src.rpm",
    ]

    def test_header_sizes(self):
        for basename in self.RPMFILES:
            fn = os.path.join(os.path.dirname(__file__), 'data/rpms', basename)

            # the file length we want to match
            st = os.stat(fn)
            file_length = st.st_size

            # An rpm consists of: lead, signature, header, archive
            s_lead, s_sig = koji.find_rpm_sighdr(fn)
            ofs = s_lead + s_sig
            s_hdr = koji.rpm_hdr_size(fn, ofs)

            # The signature can tell use the size of header+payload
            # try LONGSIZE first, fall back to 32bit SIZE
            sighdr = koji.rip_rpm_sighdr(fn)
            rh = koji.RawHeader(sighdr)
            size = None
            try:
                tag = rpm.RPMTAG_LONGSIGSIZE
                size = rh.get(tag)
            except NameError:
                pass
            if size is None:
                size = rh.get(SIGTAG_SIZE)

            # Expected file size
            calc_size = s_lead + s_sig + size
            self.assertEqual(calc_size, file_length)

            # The following bit uses rpmlib to read the header, which advances the file
            # pointer past it. This is the same approach rpm2cpio uses.
            fd = os.open(fn, os.O_RDONLY)
            try:
                os.lseek(fd, s_lead + s_sig, 0)  # seek to header start
                hdr, h_start = rpm.readHeaderFromFD(fd)
                p_offset = os.lseek(fd, 0, os.SEEK_CUR)
            finally:
                os.close(fd)
            expect_payload = s_lead + s_sig + s_hdr
            if not hdr:
                raise Exception("rpm did not return a header")
            self.assertEqual(p_offset, expect_payload)
