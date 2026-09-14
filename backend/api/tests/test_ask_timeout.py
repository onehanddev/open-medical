"""Check embedding failures without sending queries to Jina."""
import ast
from pathlib import Path
import unittest
from unittest.mock import Mock
import requests
from fastapi import HTTPException

class EmbeddingTests(unittest.TestCase):
    def function(self, post):
        path = Path(__file__).resolve().parents[1] / 'src/ask/router.py'
        fn = next(n for n in ast.parse(path.read_text()).body
                  if isinstance(n, ast.FunctionDef) and n.name == 'create_query_embedding')
        scope = dict(requests=Mock(post=post, exceptions=requests.exceptions),
                     JINA_API_KEY='test', HTTPException=HTTPException)
        exec(compile(ast.Module(body=[fn], type_ignores=[]), str(path), 'exec'), scope)
        return scope['create_query_embedding']

    def test_finite_timeout_and_success(self):
        response = Mock()
        response.json.return_value = {'data': [{'embedding': [0.1]}]}
        post = Mock(return_value=response)
        self.assertEqual(self.function(post)('test'), [0.1])
        self.assertEqual(post.call_args.kwargs.get('timeout'), (5, 30))

    def test_failures(self):
        for exception, status in [(requests.exceptions.ReadTimeout(), 504),
                                  (requests.exceptions.ConnectionError(), 502),
                                  (requests.exceptions.HTTPError(), 502)]:
            with self.subTest(status=status, exception=type(exception).__name__):
                with self.assertRaises(HTTPException) as error:
                    self.function(Mock(side_effect=exception))('test')
                self.assertEqual(error.exception.status_code, status)
