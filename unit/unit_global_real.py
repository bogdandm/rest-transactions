import hashlib
import json
from multiprocessing import Process
from pathlib import Path
from random import randint
from unittest import TestCase

import gevent
import gevent.monkey
import gevent.queue
import requests
from jsonschema import validate

from controller import rest_service
from controller.transaction_daemon import socket_api
from sql_transactions import rest_service_example

gevent.monkey.patch_all()

ROOT_PATH = (Path(__file__) / ".." / "..").resolve().absolute()

with open(str(ROOT_PATH / "unit" / "unit.global.real.json")) as f:
    CONFIG = json.load(f)
ENTRY_POINT = CONFIG["entry_point"]

with open(str(ROOT_PATH / "unit" / "status.schema")) as f:
    STATUS_SCHEMA = json.load(f)


def generate_transaction(conf):
    return {
        "timeout": conf["global_timeout"],
        "actions": [
            {
                "_id": f"Service{n}_POST_{rand_x}",
                "service": {
                    "url": f"http://localhost:501{n}/api",
                    "timeout": randint(*conf["service_local_timeout"])
                },
                "url": f"/{rand_x}",
                "method": "POST",
                "data": {
                    "array": [randint(x, x ** 2) for x in range(randint(10, 20))],
                    "str": hashlib.sha256(bytes(randint(10 ** 6, 10 ** 7))).hexdigest()
                },
                "headers": {}
            } for rand_x, n in map(
                lambda n: (randint(0, 1024), n),
                range(conf["services"])
            )]
    }


class GlobalTestReal(TestCase):
    @classmethod
    def setUpClass(cls):
        pass

    @classmethod
    def tearDownClass(cls):
        pass

    def setUp(self):
        print(self._testMethodName)
        self.config = CONFIG[self._testMethodName]

        self.controller = Process(
            target=socket_api.main,
            args=[(
                '--no_log',
                '--no_sse'
            )]
        )
        self.controller_api = Process(
            target=rest_service.main,
            args=[(
                '-P', str((ROOT_PATH / "controller").resolve().absolute()),
                '--no_log'
            )]
        )
        self.services = [
            Process(
                target=rest_service_example.main,
                args=[(
                    '-n', str(n),
                    '-P', str((ROOT_PATH / "service_example").resolve().absolute()),
                    '--no_log',
                    # '--no_sse'
                )]
            ) for n in range(self.config["services"])]

        self.controller.start()
        self.controller_api.start()
        for p in self.services: p.start()
        gevent.sleep(1)

        if "count" in self.config:
            self.transaction = None
            self.transactions = [generate_transaction(self.config) for i in range(self.config["count"])]
        else:
            self.transaction = generate_transaction(self.config)
            print(json.dumps(self.transaction, indent=4))
            self.transactions = [self.transaction]

    def tearDown(self):
        for p in self.services: p.terminate()
        self.controller_api.terminate()
        self.controller.terminate()
        gevent.sleep(1)

    def single_transaction(self, transaction, duration, wait_times=20):
        rv = requests.post(ENTRY_POINT, json=transaction)
        self.assertTrue(rv.ok, rv.json())
        rv_json = rv.json()
        uri = rv_json["uri"]  # type: str
        print(uri)
        _id = rv_json["ID"]

        rv = requests.get(uri)
        self.assertTrue(rv.ok, rv.json())
        status = rv.json()
        validate(status, STATUS_SCHEMA)
        self.assertNotEqual(status[_id]["global"], "FAIL")
        self.assertNotEqual(status[_id]["global"], "DONE")

        gevent.sleep(duration)

        for i in range(wait_times):
            rv = requests.get(uri)
            self.assertTrue(rv.ok, rv.json())
            status = rv.json()
            validate(status, STATUS_SCHEMA)
            if status[_id]["global"] == "DONE":
                break
            if status[_id]["global"] == "FAIL":
                self.fail("Transaction fail")
            gevent.sleep(0.5)  # sum sleep wait_times * 0.5s
        else:
            self.fail("Transaction is executed too long")

    def test_one(self):
        self.single_transaction(self.transaction, 20)
