import json as json_lib
from unittest import TestCase

from flask.testing import FlaskClient

from tools.flask import EmptyApp
from tools.flask.decorators import *

schema = {
    "$schema": "http://json-schema.org/draft-04/schema#",
    "type": "object",
    "properties": {
        "x": {
            "type": "string"
        },
        "y": {
            "type": "string"
        }
    },
    "required": [
        "x",
        "y"
    ]
}


class JSONFlaskClient(FlaskClient):
    json = True

    def open(self, *args, **kwargs):
        if self.json:
            kwargs["content_type"] = "application/json"
            kwargs["data"] = json_lib.dumps(kwargs.get("data"))
        return super().open(*args, **kwargs)


class TestApp(EmptyApp):
    def __init__(self, root_path, app_root):
        super().__init__(root_path, app_root)
        self.db = {chr(ord('a') + i): i for i in range(ord('z') - ord('a'))}

        @self.route("/nocache")
        @nocache
        def test_nocache():
            return "OK"

        @self.route("/validate", methods=["POST"])
        @validate(schema)
        def test_validate(data):
            return data['x'] + data['y']

        @self.route("/json")
        @json(id_field="ch")
        def test_json():
            ch = request.args["ch"]
            if ch in self.db:
                return {"ch": ch, "ord": self.db[ch]}
            else:
                return 404


class TestFlask(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = TestApp(".", "/api")
        cls.server.test_client_class = JSONFlaskClient
        cls.client = cls.server.test_client(use_cookies=False)

    def setUp(self):
        print(self._testMethodName)

    def tearDown(self):
        print("=-=")

    def test_nocache(self):
        rv = self.client.get("/api/nocache")
        h = {'Cache-Control': 'no-cache, no-store, must-revalidate', 'Pragma': 'no-cache',
             'Access-Control-Allow-Origin': '*', 'Expires': '0'}
        for k, v in h.items():
            self.assertTrue(rv.headers[k], v)

    def test_validate(self):
        rv = self.client.post("/api/validate", data={"x": "hello ", "y": "world"})
        self.assertEqual(rv.data, b"hello world")

    def test_json(self):
        rv = self.client.get("/api/json?ch=b")
        data = json_lib.loads(str(rv.data, encoding="utf-8"))
        self.assertEqual(data, {'ord': 1, 'uri': 'http://localhost/api/json/b', 'ch': 'b'})

    def test404(self):
        rv = self.client.get("/")
        self.assertEqual(rv.status, '404 Page not found')
