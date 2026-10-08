import io
import os
import sys
import types
import unittest
import importlib.util

# Setup mock flask environment if flask is not installed locally
if 'flask' not in sys.modules:
    flask_mod = types.ModuleType('flask')
    
    class MockFlask:
        def __init__(self, name):
            self.config = {}
            self.routes = {}
            self.errorhandlers = {}
        def errorhandler(self, code):
            def decorator(f):
                self.errorhandlers[code] = f
                return f
            return decorator
        def route(self, rule, methods=None):
            def decorator(f):
                self.routes[rule] = f
                return f
            return decorator

    class MockRequest:
        def __init__(self):
            self.files = {}

    flask_mod.Flask = MockFlask
    flask_mod.request = MockRequest()
    def jsonify(data):
        return data
    flask_mod.jsonify = jsonify
    sys.modules['flask'] = flask_mod

current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
api_dir = os.path.join(project_root, "api")
if api_dir not in sys.path:
    sys.path.insert(0, api_dir)

spec = importlib.util.spec_from_file_location('index', os.path.join(api_dir, 'index.py'))
index_mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(index_mod)
import flask


class MockFile:
    def __init__(self, filename, content_bytes):
        self.filename = filename
        self.content_bytes = content_bytes
    def read(self):
        return self.content_bytes


class TestEcoGenAPI(unittest.TestCase):
    """Integration test suite for EcoGen Diagnostics API endpoints."""

    def test_health_endpoint(self):
        """Verify GET /api/health returns 200 with service confirmation."""
        res, code = index_mod.health()
        self.assertEqual(code, 200)
        self.assertTrue(res.get("ok"))
        self.assertEqual(res.get("service"), "EcoGen Diagnostics")

    def test_upload_missing_file_field(self):
        """Verify POST /api/upload returns 400 when 'file' is not in request.files."""
        flask.request.files = {}
        res, code = index_mod.upload()
        self.assertEqual(code, 400)
        self.assertIn("No file uploaded", res["error"])

    def test_upload_invalid_extension(self):
        """Verify POST /api/upload returns 400 when file is not .csv."""
        flask.request.files = {
            "file": MockFile("genotypes.txt", b"some,text,data")
        }
        res, code = index_mod.upload()
        self.assertEqual(code, 400)
        self.assertIn("Only .csv files are supported", res["error"])

    def test_upload_empty_file(self):
        """Verify POST /api/upload returns 400 when file is 0 bytes."""
        flask.request.files = {
            "file": MockFile("empty.csv", b"")
        }
        res, code = index_mod.upload()
        self.assertEqual(code, 400)
        self.assertIn("empty", res["error"].lower())

    def test_upload_oversized_file(self):
        """Verify POST /api/upload returns 413 when file exceeds 4 MB."""
        oversized_bytes = b"A" * (4 * 1024 * 1024 + 10)
        flask.request.files = {
            "file": MockFile("large.csv", oversized_bytes)
        }
        res, code = index_mod.upload()
        self.assertEqual(code, 413)
        self.assertIn("exceeds the 4 MB limit", res["error"])

    def test_upload_valid_csv(self):
        """Verify POST /api/upload successfully processes valid CSV data."""
        csv_content = (
            b"Individual_ID,Locus1_A1,Locus1_A2,Locus2_A1,Locus2_A2\n"
            b"Ind_1,142,150,100,100\n"
            b"Ind_2,142,142,100,104\n"
            b"Ind_3,150,150,104,104\n"
        )
        flask.request.files = {
            "file": MockFile("population.csv", csv_content)
        }
        res, code = index_mod.upload()
        self.assertEqual(code, 200)
        self.assertIn("status", res)
        self.assertIn("summary", res)
        self.assertEqual(res["summary"]["sample_count"], 3)
        self.assertEqual(res["summary"]["locus_count"], 2)


if __name__ == "__main__":
    unittest.main()
