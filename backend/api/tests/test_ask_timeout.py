"""Check Cloudflare embedding contracts without external requests."""
import ast
from pathlib import Path
import unittest
from unittest.mock import Mock
from types import SimpleNamespace
import requests
from fastapi import HTTPException

class EmbeddingTests(unittest.TestCase):
    def function(self, post):
        path = Path(__file__).resolve().parents[1] / 'src/ask/router.py'
        fn = next(n for n in ast.parse(path.read_text()).body
                  if isinstance(n, ast.FunctionDef) and n.name == 'create_query_embedding')
        scope = dict(requests=Mock(post=post, exceptions=requests.exceptions),
                     cloudflare_acccount_id='test-account',
                     cloudflare_api_token='test-token', HTTPException=HTTPException)
        exec(compile(ast.Module(body=[fn], type_ignores=[]), str(path), 'exec'), scope)
        return scope['create_query_embedding']

    def test_finite_timeout_and_success(self):
        response = Mock()
        response.json.return_value = {'success': True, 'result': {'data': [[0.1]]}}
        post = Mock(return_value=response)
        self.assertEqual(self.function(post)('test'), [0.1])
        self.assertEqual(post.call_args.kwargs.get('timeout'), (5, 30))
        self.assertEqual(post.call_args.kwargs['json'], {'text': ['test']})
        self.assertTrue(post.call_args.args[0].endswith('/ai/run/@cf/baai/bge-m3'))

    def test_provider_failure(self):
        response = Mock()
        response.json.return_value = {'success': False, 'result': None}
        with self.assertRaises(HTTPException) as error:
            self.function(Mock(return_value=response))('test')
        self.assertEqual(error.exception.status_code, 502)

    def test_failures(self):
        for exception, status in [(requests.exceptions.ReadTimeout(), 504),
                                  (requests.exceptions.ConnectionError(), 502),
                                  (requests.exceptions.HTTPError(), 502)]:
            with self.subTest(status=status, exception=type(exception).__name__):
                with self.assertRaises(HTTPException) as error:
                    self.function(Mock(side_effect=exception))('test')
                self.assertEqual(error.exception.status_code, status)


class WorkerEmbeddingTests(unittest.TestCase):
    def functions(self, post):
        path = Path(__file__).resolve().parents[2] / 'worker/s3_upload_fetch.py'
        functions = [n for n in ast.parse(path.read_text()).body
                     if isinstance(n, ast.FunctionDef)
                     and n.name in {'cloudflare_embed', 'create_embeddings'}]
        scope = dict(requests=Mock(post=post), time=Mock(),
                     cloudflare_acccount_id='test-account', cloudflare_api_token='test-token')
        exec(compile(ast.Module(body=functions, type_ignores=[]), str(path), 'exec'), scope)
        return scope

    def test_batches_preserve_chunk_order_and_all_vectors(self):
        def respond(url, **kwargs):
            self.assertTrue(url.endswith('/ai/run/@cf/baai/bge-m3'))
            self.assertEqual(kwargs['timeout'], (5, 30))
            response = Mock()
            response.json.return_value = {
                'success': True,
                'result': {'data': [[float(text)] for text in kwargs['json']['text']]},
            }
            return response

        post = Mock(side_effect=respond)
        scope = self.functions(post)
        chunks = [SimpleNamespace(page_content=str(i)) for i in range(101)]
        self.assertEqual(scope['create_embeddings'](chunks), [[float(i)] for i in range(101)])
        self.assertEqual([len(call.kwargs['json']['text']) for call in post.call_args_list], [100, 1])

    def test_empty_chunks_make_no_request(self):
        post = Mock()
        self.assertEqual(self.functions(post)['create_embeddings']([]), [])
        post.assert_not_called()

    def test_reject_failed_or_incomplete_batch(self):
        for body in [{'success': False}, {'success': True, 'result': {'data': []}}]:
            with self.subTest(body=body):
                response = Mock()
                response.json.return_value = body
                scope = self.functions(Mock(return_value=response))
                with self.assertRaises(ValueError):
                    scope['create_embeddings']([SimpleNamespace(page_content='test')])
