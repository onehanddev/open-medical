"""Check the signing contract without AWS credentials or network calls."""
import ast
from pathlib import Path
import unittest
from unittest.mock import Mock
from uuid import uuid4


class UploadFilenameTests(unittest.TestCase):
    def test_each_upload_preserves_filename_with_a_unique_key(self):
        router = Path(__file__).resolve().parents[1] / 'src/upload/router.py'
        tree = ast.parse(router.read_text())
        endpoint = next(node for node in tree.body
                        if isinstance(node, ast.FunctionDef) and node.name == 'get_presigned_url')
        endpoint.decorator_list = []
        signer = Mock(return_value='https://storage.example.test/signed')
        scope = dict(Query=lambda *args, **kwargs: None, uuid4=uuid4,
                     create_presigned_url=signer, aws_bucket_name='test-bucket',
                     aws_region_name='test-region', aws_expiry=3600)
        exec(compile(ast.Module(body=[endpoint], type_ignores=[]), str(router), 'exec'), scope)
        filename = 'Book + notes & résumé.pdf'
        for _ in range(2):
            self.assertEqual(scope['get_presigned_url'](filename),
                             'https://storage.example.test/signed')
        keys = [call.args[1] for call in signer.call_args_list]
        self.assertNotEqual(*keys)
        for key in keys:
            self.assertEqual(key.split('/', 2)[2], filename)


if __name__ == '__main__':
    unittest.main()
