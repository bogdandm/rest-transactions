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
from service_example import rest_service_dummy

gevent.monkey.patch_all()

ROOT_PATH = (Path(__file__) / ".." / "..").resolve().absolute()

with open(str(ROOT_PATH / "unit" / "unit.global.json")) as f:
    CONFIG = json.load(f)
ENTRY_POINT = CONFIG["entry_point"]
with open(str(ROOT_PATH / "unit" / "status.schema")) as f:
    STATUS_SCHEMA = json.load(f)


def generate_transaction(conf):
    return {
        "timeout": conf["global_timeout"],
        "actions": [
            {
                "_id": "Service%i_GET_%i" % (n, i),
                "service": {
                    "url": "http://localhost:501%i/api" % n,
                    "timeout": randint(*conf["service_local_timeout"])
                },
                "url": "/%i" % i,
                "method": "GET",
                "data": {},
                "headers": {}
            } for i, n, service in map(
                lambda n_i: (randint(0, 1024), *n_i),
                enumerate(conf["services"])
            )]
    }


def max_transaction_duration(conf):
    work = max(map(
        lambda s: s["work"][1],
        conf["services"]
    ))
    ping = max(map(
        lambda s: s["work"][1],
        conf["services"]
    ))
    return work + ping + 2


class GlobalTest(TestCase):
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
                target=rest_service_dummy.main,
                args=[(
                    '-n', str(n),
                    '-p', str(service["ping"][0]), str(service["ping"][1]),
                    '-w', str(service["work"][0]), str(service["work"][1]),
                    '-P', str((ROOT_PATH / "service_example").resolve().absolute()),
                    '--no_log',
                    '--no_sse'
                )]
            ) for n, service in enumerate(self.config["services"])]

        self.controller.start()
        self.controller_api.start()
        for p in self.services: p.start()
        gevent.sleep(1)

        if "count" in self.config:
            self.transaction = None
            self.transactions = [generate_transaction(self.config) for i in range(self.config["count"])]
        else:
            self.transaction = generate_transaction(self.config)
            self.transactions = [self.transaction]

    def tearDown(self):
        for p in self.services: p.terminate()
        self.controller_api.terminate()
        self.controller.terminate()
        gevent.sleep(1)

    def test_simple(self):
        self.single_transaction(self.transaction, max_transaction_duration(self.config))

    def test_spam_1(self):
        self.spam_transaction()

    # @skip("")
    def test_spam_2(self):
        self.spam_transaction(100)

    # @skip("")
    def test_spam_3(self):
        self.spam_transaction(1000)

    def single_transaction(self, transaction, duration, wait_times=20):
        rv = requests.post(ENTRY_POINT, json=transaction)
        self.assertTrue(rv.ok, rv.json())
        rv_json = rv.json()
        uri = rv_json["uri"]  # type: str
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

    def spam_transaction(self, wait_times=20):
        duration = max_transaction_duration(self.config)

        def spawn(*args, sleep: float = 0, **kwargs):
            th = gevent.spawn(*args, **kwargs)
            gevent.sleep(sleep)
            return th

        threads = [spawn(self.single_transaction, self.transactions[i], duration, wait_times, sleep=0.1) for i in
                   range(self.config["count"])]
        gevent.joinall(threads, raise_error=True)
        for th in threads:
            if th.exception:
                raise th.exception
