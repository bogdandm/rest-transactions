import gevent.monkey

gevent.monkey.patch_all()

import json
from multiprocessing import Process
from pathlib import Path
from random import randint
from unittest import TestCase

import requests
from jsonschema import validate

from controller import rest_service
from controller.transaction_daemon import socket_api
from service_example import rest_service_dummy

with open("unit.global.json") as f:
	config = json.load(f)
ENTRY_POINT = config["entry_point"]
with open("status.schema") as f:
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


class GlobalTest(TestCase):
	@classmethod
	def setUpClass(cls):
		pass

	@classmethod
	def tearDownClass(cls):
		pass

	def setUp(self):
		print(self._testMethodName)
		self.config = config[self._testMethodName]

		self.controller = Process(
			target=socket_api.main,
			args=(True,)
		)
		self.controller_api = Process(
			target=rest_service.main,
			args=(str((Path(".") / ".." / "controller").resolve().absolute()),)
		)
		self.services = [
			Process(
				target=rest_service_dummy.main,
				args=(
					True,
					str((Path(".") / ".." / "service_example").resolve().absolute()),
					(
						'-n', str(n),
						'-p', str(service["ping"][0]), str(service["ping"][1]),
						'-w', str(service["work"][0]), str(service["work"][1]),
					)
				)
			) for n, service in enumerate(self.config["services"])]

		self.controller.start()
		gevent.sleep(0.5)
		self.controller_api.start()
		gevent.sleep(0.2)
		for p in self.services: p.start()

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

	def test_simple(self):
		rv = requests.post(ENTRY_POINT, json=self.transaction)
		self.assertTrue(rv.ok)
		rv_json = rv.json()
		uri = rv_json["uri"]  # type: str
		_id = rv_json["ID"]

		rv = requests.get(uri)
		self.assertTrue(rv.ok)
		status = rv.json()
		validate(status, STATUS_SCHEMA)
		self.assertNotEqual(status[_id]["global"], "FAIL")
		self.assertNotEqual(status[_id]["global"], "DONE")

		gevent.sleep(2 * max(map(
			lambda s: s["work"][1],
			self.config["services"]
		)))

		rv = requests.get(uri)
		self.assertTrue(rv.ok)
		status = rv.json()
		validate(status, STATUS_SCHEMA)
		self.assertEqual(status[_id]["global"], "DONE")
