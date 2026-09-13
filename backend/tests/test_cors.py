"""Check browser preflights using the application's actual middleware configuration."""
import ast
from pathlib import Path
import unittest
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.testclient import TestClient

class CorsTests(unittest.TestCase):
    def test_json_post_preflight(self):
        path = Path(__file__).resolve().parents[1] / 'main.py'
        tree = ast.parse(path.read_text())
        middleware = [node for node in tree.body if isinstance(node, ast.Expr)
                      and isinstance(node.value, ast.Call)
                      and isinstance(node.value.func, ast.Attribute)
                      and node.value.func.attr == 'add_middleware']
        app = FastAPI()
        exec(compile(ast.Module(body=middleware, type_ignores=[]), str(path), 'exec'),
             dict(app=app, CORSMiddleware=CORSMiddleware))
        with TestClient(app) as client:
            response = client.options('/ask/', headers={
                'Origin': 'http://localhost:5173',
                'Access-Control-Request-Method': 'POST',
                'Access-Control-Request-Headers': 'content-type',
            })
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.headers['access-control-allow-origin'], 'http://localhost:5173')
        self.assertIn('POST', response.headers['access-control-allow-methods'])
