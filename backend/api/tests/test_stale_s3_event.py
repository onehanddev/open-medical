"""Regression coverage for S3 creation events whose object was later deleted."""

import ast
from pathlib import Path
import unittest
from unittest.mock import Mock

from botocore.exceptions import ClientError


WORKER = Path(__file__).resolve().parents[1] / "workers" / "s3_upload_fetch.py"


class StaleS3EventTests(unittest.TestCase):
    def load_reader(self, s3_client):
        tree = ast.parse(WORKER.read_text())
        reader = next(
            node
            for node in tree.body
            if isinstance(node, ast.FunctionDef)
            and node.name == "read_s3_object"
        )
        scope = {"s3": s3_client, "ClientError": ClientError, "logging": Mock()}
        exec(
            compile(ast.Module(body=[reader], type_ignores=[]), str(WORKER), "exec"),
            scope,
        )
        return scope["read_s3_object"], scope["logging"]

    def test_missing_object_is_skipped(self):
        error = ClientError(
            {"Error": {"Code": "NoSuchKey", "Message": "missing"}},
            "GetObject",
        )
        reader, logger = self.load_reader(Mock(get_object=Mock(side_effect=error)))

        self.assertIsNone(reader("openmedical", "pdf/deleted.pdf"))
        logger.warning.assert_called_once()

    def test_existing_object_is_returned(self):
        body = Mock()
        body.read.return_value = b"pdf bytes"
        reader, _ = self.load_reader(
            Mock(get_object=Mock(return_value={"Body": body}))
        )

        self.assertEqual(reader("openmedical", "pdf/current.pdf"), b"pdf bytes")

    def test_other_s3_errors_still_fail(self):
        error = ClientError(
            {"Error": {"Code": "AccessDenied", "Message": "denied"}},
            "GetObject",
        )
        reader, _ = self.load_reader(Mock(get_object=Mock(side_effect=error)))

        with self.assertRaises(ClientError):
            reader("openmedical", "pdf/current.pdf")


if __name__ == "__main__":
    unittest.main()
