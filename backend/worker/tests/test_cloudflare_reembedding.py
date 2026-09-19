"""Exercise the script's real functions with a local database and fake Cloudflare."""
import ast
import logging
import math
from pathlib import Path
import tempfile
import sys
import unittest
from unittest.mock import Mock

import requests
from sqlalchemy import JSON, Column, Integer, String, create_engine, select, update
from sqlalchemy.orm import declarative_base, sessionmaker


Base = declarative_base()


class Chunk(Base):
    __tablename__ = "document_chunks"
    id = Column(Integer, primary_key=True)
    content = Column(String, nullable=False)
    embeddings = Column(JSON, nullable=False)


class ReembeddingTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.engine = create_engine(f"sqlite:///{self.directory.name}/test.db")
        Base.metadata.create_all(self.engine)
        self.sessions = sessionmaker(bind=self.engine)
        with self.sessions.begin() as db:
            db.add_all([Chunk(id=i, content=str(i), embeddings=[-1.0] * 1024)
                        for i in range(1, 62)])
        path = Path(__file__).resolve().parents[1] / "cloudflare_em_test.py"
        functions = [n for n in ast.parse(path.read_text()).body
                     if isinstance(n, ast.FunctionDef)]
        self.post = Mock(side_effect=self.respond)
        self.scope = dict(
            SessionLocal=self.sessions, DocumentChunks=Chunk, select=select,
            update=update, logging=logging, math=math,
            requests=Mock(post=self.post), time=Mock(),
            cloudflare_acccount_id="test", cloudflare_api_token="test",
        )
        exec(compile(ast.Module(body=functions, type_ignores=[]), str(path), "exec"), self.scope)

    def tearDown(self):
        self.engine.dispose()
        self.directory.cleanup()

    def respond(self, url, **kwargs):
        self.assertEqual(self.engine.pool.checkedout(), 0,
                         "A database transaction is held during the embedding request")
        response = Mock(ok=True)
        response.json.return_value = {
            "success": True,
            "result": {"data": [[float(text)] * 1024 for text in kwargs["json"]["text"]]},
        }
        return response

    def test_releases_connection_during_embedding_and_keeps_id_mapping(self):
        self.scope["get_all_chunks_from_db"]()
        with self.sessions() as db:
            for chunk in db.scalars(select(Chunk)):
                self.assertEqual(chunk.embeddings, [float(chunk.id)] * 1024)
        self.assertEqual(self.post.call_count, 2)
        self.scope['time'].sleep.assert_called_once_with(40)
        self.assertEqual(self.post.call_args.kwargs['timeout'], (5, 60))

    def assert_original_embeddings(self):
        with self.sessions() as db:
            for chunk in db.scalars(select(Chunk)):
                self.assertEqual(chunk.embeddings, [-1.0] * 1024)
        self.assertEqual(self.engine.pool.checkedout(), 0)

    def test_no_connection_during_rate_limit_sleep(self):
        self.scope['time'].sleep.side_effect = lambda _: self.assertEqual(
            self.engine.pool.checkedout(), 0)
        self.scope['get_all_chunks_from_db']()

    def test_failed_second_batch_leaves_database_unchanged(self):
        first = self.respond('', json={'text': [str(i) for i in range(1, 61)]})
        self.post.side_effect = [first, requests.exceptions.ReadTimeout('timed out')]
        with self.assertRaises(requests.exceptions.ReadTimeout):
            self.scope['get_all_chunks_from_db']()
        self.assert_original_embeddings()

    def test_rejects_invalid_provider_results_without_writes(self):
        for body in [
            {'success': False},
            {'success': True, 'result': {'data': []}},
            {'success': True, 'result': {'data': [[1.0]] * 60}},
            {'success': True, 'result': {'data': [[float('nan')] * 1024] * 60}},
        ]:
            with self.subTest(body_type=str(body)[:80]):
                response = Mock(ok=True)
                response.json.return_value = body
                self.post.side_effect = None
                self.post.return_value = response
                with self.assertRaises(ValueError):
                    self.scope['get_all_chunks_from_db']()
                self.assert_original_embeddings()

    def test_changed_or_deleted_chunk_rolls_back_prior_updates(self):
        for delete in (False, True):
            with self.subTest(delete=delete):
                def respond(url, **kwargs):
                    response = self.respond(url, **kwargs)
                    # Modify the final chunk after the snapshot was read.
                    if kwargs['json']['text'] == ['61']:
                        with self.sessions.begin() as db:
                            chunk = db.get(Chunk, 61)
                            if delete:
                                db.delete(chunk)
                            else:
                                chunk.content = 'changed'
                    return response
                self.post.side_effect = respond
                with self.assertRaisesRegex(RuntimeError, 'changed or deleted'):
                    self.scope['get_all_chunks_from_db']()
                self.assert_original_embeddings()
                with self.sessions.begin() as db:
                    chunk = db.get(Chunk, 61)
                    if chunk:
                        chunk.content = '61'

    def test_new_chunk_does_not_shift_existing_mapping(self):
        def respond(url, **kwargs):
            response = self.respond(url, **kwargs)
            if kwargs['json']['text'] == ['61']:
                with self.sessions.begin() as db:
                    db.add(Chunk(id=100, content='100', embeddings=[-1.0] * 1024))
            return response
        self.post.side_effect = respond
        self.scope['get_all_chunks_from_db']()
        with self.sessions() as db:
            self.assertEqual(db.get(Chunk, 61).embeddings, [61.0] * 1024)
            self.assertEqual(db.get(Chunk, 100).embeddings, [-1.0] * 1024)

    def test_empty_database_does_not_call_provider(self):
        with self.sessions.begin() as db:
            db.query(Chunk).delete()
        self.scope['get_all_chunks_from_db']()
        self.post.assert_not_called()

    def test_main_logs_traceback_and_exits_nonzero(self):
        path = Path(__file__).resolve().parents[1] / 'cloudflare_em_test.py'
        main = next(n for n in ast.parse(path.read_text()).body if isinstance(n, ast.If))
        logger = Mock()
        scope = dict(__name__='__main__', logging=logger, sys=sys,
                     get_all_chunks_from_db=Mock(side_effect=RuntimeError('database failed')))
        with self.assertRaises(SystemExit) as error:
            exec(compile(ast.Module(body=[main], type_ignores=[]), str(path), 'exec'), scope)
        self.assertEqual(error.exception.code, 1)
        logger.exception.assert_called_once()


if __name__ == "__main__":
    unittest.main()
