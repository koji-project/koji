import mock
import time
import unittest
from collections import defaultdict

import koji
import kojihub

DP = kojihub.DeleteProcessor
QP = kojihub.QueryProcessor
UP = kojihub.UpdateProcessor


class TestDeleteBuild(unittest.TestCase):
    def getDelete(self, *args, **kwargs):
        delete = DP(*args, **kwargs)
        delete.execute = mock.MagicMock()
        self.deletes.append(delete)
        return delete

    def getQuery(self, *args, **kwargs):
        query = QP(*args, **kwargs)
        query.execute = self.query_execute
        self.queries.append(query)
        return query

    def getUpdate(self, *args, **kwargs):
        update = UP(*args, **kwargs)
        update.execute = mock.MagicMock()
        self.updates.append(update)
        return update

    def setUp(self):
        self.DeleteProcessor = mock.patch(
            "kojihub.kojihub.DeleteProcessor", side_effect=self.getDelete
        ).start()
        self.deletes = []
        self.QueryProcessor = mock.patch(
            "kojihub.kojihub.QueryProcessor", side_effect=self.getQuery
        ).start()
        self.queries = []
        self.query_execute = mock.MagicMock()
        self.UpdateProcessor = mock.patch(
            "kojihub.kojihub.UpdateProcessor", side_effect=self.getUpdate
        ).start()
        self.updates = []
        self.context_db = mock.patch("kojihub.db.context").start()
        self.context_db.session.assertLogin = mock.MagicMock()
        self.context_db.event_id = 42
        self.context_db.session.user_id = 24
        self.get_build = mock.patch("kojihub.kojihub.get_build").start()
        self._delete_build = mock.patch("kojihub.kojihub._delete_build").start()
        self.get_user = mock.patch("kojihub.kojihub.get_user").start()
        self.context = mock.patch("kojihub.kojihub.context").start()
        self.context.session.assertPerm = mock.MagicMock()
        self.binfo = {
            "id": "BUILD ID",
            "state": koji.BUILD_STATES["COMPLETE"],
            "name": "test_nvr",
            "nvr": "test_nvr-3.3-20.el8",
            "version": "3.3",
            "release": "20",
            "volume_id": 1,
            "volume_name": 'testvol',
            "draft": False
        }

    def tearDown(self):
        mock.patch.stopall()

    def test_delete_build_raise_error(self):
        references = ["tags", "rpms", "archives", "component_of"]
        for ref in references:
            context = mock.MagicMock()
            context.session.return_value = context

            with mock.patch("kojihub.kojihub.build_references") as refs:
                retval = defaultdict(dict)
                retval[ref] = True
                refs.return_value = retval
                with self.assertRaises(koji.GenericError):
                    kojihub.delete_build(build="", strict=True)

    def test_delete_build_return_false(self):
        references = ["tags", "rpms", "archives", "component_of"]
        for ref in references:
            context = mock.MagicMock()
            context.session.return_value = context

            with mock.patch("kojihub.kojihub.build_references") as refs:
                retval = defaultdict(dict)
                retval[ref] = True
                refs.return_value = retval
                assert kojihub.delete_build(build="", strict=False) is False

    def test_delete_build_check_last_used_raise_error(self):
        references = ["tags", "rpms", "archives", "component_of", "last_used"]
        for ref in references:
            context = mock.MagicMock()
            context.session.return_value = context

            with mock.patch("kojihub.kojihub.build_references") as refs:
                retval = defaultdict(dict)
                if ref == "last_used":
                    retval[ref] = time.time() + 100
                    refs.return_value = retval
                    self.assertFalse(kojihub.delete_build(build="", strict=False))

    @mock.patch("kojihub.kojihub.build_references")
    def test_delete_build_lazy_refs(self, buildrefs):
        """Test that we can handle lazy return from build_references"""
        self.get_user.return_value = {
            "authtype": 2,
            "id": 1,
            "krb_principal": None,
            "krb_principals": [],
            "name": "kojiadmin",
            "status": 0,
            "usertype": 0,
        }
        buildrefs.return_value = {"tags": []}
        self.get_build.return_value = self.binfo
        kojihub.delete_build(build=self.binfo, strict=True)

        # no build refs, so we should have called _delete_build
        self._delete_build.assert_called_with(self.binfo)

    @mock.patch("os.unlink")
    @mock.patch("koji.util.rmtree")
    def test_delete_build_queries(self, rmtree, unlink):
        self.query_execute.side_effect = [
            [(123,)],  # rpm ids
            {'id': 0, 'name': 'DEFAULT'},  # volume DEFAULT
            [{'id': 0, 'name': 'DEFAULT'},
             {'id': 1, 'name': 'testvol'},
             {'id': 2, 'name': 'other'}]  # list_volumes()
        ]

        kojihub._delete_build(self.binfo)

        self.assertEqual(len(self.queries), 3)
        query = self.queries[0]
        self.assertEqual(query.tables, ["rpminfo"])
        self.assertEqual(query.joins, None)
        self.assertEqual(query.clauses, ["build_id=%(build_id)i"])
        self.assertEqual(query.columns, ["id"])

        self.assertEqual(len(self.deletes), 2)
        delete = self.deletes[0]
        self.assertEqual(delete.table, "rpmsigs")
        self.assertEqual(delete.clauses, ["rpm_id=%(rpm_id)i"])

        delete = self.deletes[1]
        self.assertEqual(delete.table, "rpm_checksum")
        self.assertEqual(delete.clauses, ["rpm_id=%(rpm_id)i"])

        self.assertEqual(len(self.updates), 2)
        update = self.updates[0]
        self.assertEqual(update.table, "tag_listing")
        self.assertEqual(update.values, {"build_id": self.binfo["id"]})
        self.assertEqual(update.data, {"revoke_event": 42, "revoker_id": 24})
        self.assertEqual(update.rawdata, {"active": "NULL"})
        self.assertEqual(update.clauses, ["build_id=%(build_id)i", "active = TRUE"])

        update = self.updates[1]
        self.assertEqual(update.table, "build")
        self.assertEqual(update.values, {"build_id": self.binfo["id"]})
        self.assertEqual(update.data, {"state": 2})
        self.assertEqual(update.rawdata, {})
        self.assertEqual(update.clauses, ["id=%(build_id)i"])
