"""Exercise conversion reporting without starting the worker's SQS polling loop."""
import ast
from collections import defaultdict
from contextlib import redirect_stdout
import io
from pathlib import Path
from types import SimpleNamespace as NS
import unittest
from unittest.mock import mock_open, patch


WORKER = Path(__file__).resolve().parents[1] / 'workers' / 's3_upload_fetch.py'


class PictureDetectionTests(unittest.TestCase):
    def report(self, pictures, pages=None):
        tree = ast.parse(WORKER.read_text())
        functions = [node for node in tree.body if isinstance(node, ast.FunctionDef)]
        doc = NS(tables=[], pictures=pictures, pages=pages,
                 export_to_markdown=lambda: 'book markdown')
        namespace = dict(io=io, defaultdict=defaultdict,
                         os=NS(path=NS(dirname=lambda path: './downloads'), makedirs=lambda *a, **k: None),
                         DocumentStream=lambda **kwargs: kwargs,
                         converter=NS(convert=lambda source: NS(document=doc)))
        exec(compile(ast.Module(body=functions, type_ignores=[]), str(WORKER), 'exec'), namespace)
        with redirect_stdout(io.StringIO()) as output, patch('builtins.open', mock_open()):
            self.assertEqual(namespace['bytes_to_docling']('book.pdf', b'pdf'), 'book markdown')
        return output.getvalue()

    def test_modern_classification_and_multiple_pages(self):
        picture = NS(prov=[NS(page_no=2), NS(page_no=3)],
                     meta=NS(classification=NS(predictions=[
                         NS(class_name='bar_chart', confidence=.01),
                         NS(class_name='flow_chart', confidence=.99)])))
        report = self.report([picture])
        self.assertIn('Page 2: 📊 picture(s) Found (diagram(s))', report)
        self.assertIn('Page 3: 📊 picture(s) Found (diagram(s))', report)
        self.assertNotIn('chart(s)/graph(s)', report)

    def test_legacy_chart(self):
        picture = NS(prov=[NS(page_no=1)], annotations=[NS(predicted_classes=[
            NS(class_name='line_chart', confidence=.98)])])
        self.assertIn('picture(s) Found (chart(s)/graph(s))', self.report([picture]))

    def test_unclassified_picture_and_empty_page(self):
        picture = NS(prov=[NS(page_no=1)], annotations=[])
        report = self.report([picture], {1: None, 2: None})
        self.assertIn('Page 1: 📊 picture(s) Found (other/unclassified)', report)
        self.assertIn('Page 2: 📄 No pictures', report)

    def test_missing_provenance(self):
        self.assertIn('Page 1: 📄 No pictures', self.report([NS(prov=[])], {1: None}))

    def test_pipeline_enables_classification(self):
        tree = ast.parse(WORKER.read_text())
        options = next(node.value for node in tree.body if isinstance(node, ast.Assign)
                       and any(isinstance(target, ast.Name) and target.id == 'options'
                               for target in node.targets))
        self.assertTrue(next(ast.literal_eval(kw.value) for kw in options.keywords
                             if kw.arg == 'do_picture_classification'))


if __name__ == '__main__':
    unittest.main()
