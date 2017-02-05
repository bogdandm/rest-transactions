import json as json_lib
import traceback
from pathlib import Path
from typing import Union, Dict, List

import werkzeug.exceptions
from flask import Flask, Response, Request, make_response
from werkzeug.wsgi import DispatcherMiddleware

from tools import transform_json_types
from tools.exceptions import catalog, AException
from tools.flask_.decorators import json


def register_errors(
		app: Flask,
		custom_errors: List[AException] = None,
		debug: bool = False
):
	"""
	Create and register error handlers for HTTP errors and custom Exceptions. The data will returned in JSON.

	:param app: Flask app
	:param custom_errors: List of custom exceptions
	:param debug: If true debug information will added to response
	:return: None
	"""

	@app.errorhandler(Exception)
	@json(add_uri=False)
	def e_handler(e: Exception):
		data = {
			"code": 500,
			"description": werkzeug.exceptions.InternalServerError.description,
			"text": werkzeug.exceptions.HTTP_STATUS_CODES[500],
			**({"data": e.args} if debug else {})
		}

		if debug:
			traceback.print_exc()

		return data["code"], data

	@app.errorhandler(werkzeug.exceptions.HTTPException)
	@json(add_uri=False)
	def http_e_handler(e: werkzeug.exceptions.HTTPException):
		data = {
			"code": e.code,
			"text": str(e.code) + " " + e.name,
			"description": e.description,
			**({"data": e.response} if debug else {})
		}

		return data["code"], data

	for e in werkzeug.exceptions.default_exceptions.values():
		app.register_error_handler(e, http_e_handler)

	if custom_errors:
		def func(e: AException):
			return jsonify(e.code, {
				"code": e.n,
				"description": e.desc,
				"data": e.data
			})

		for error in custom_errors:
			app.register_error_handler(error, func)


def request_data(request_: Request):
	"""
	Get data from any type of request

	:param request_:
	:return:
	"""
	if request_.method in ("GET", "DELETE"):
		return request_.args

	if request_.is_json:
		return request_.get_json()
	return request_.form


def dejsonify(data: str, need_transform=False) -> Union[dict, list]:
	"""
	Wrapper to json_lib.loads and tools.transform_json_types functions

	:param data:
	:param need_transform:
	:return:
	"""
	data = json_lib.loads(data)
	if need_transform:
		transform_json_types(data, direction=1)
	return data


def jsonify(status: int, data: Union[dict, list], need_transform=False) -> Response:
	"""
	make_response wrapper to JSON format

	:param status:
	:param data:
	:param need_transform:
	:return:
	"""
	if need_transform:
		transform_json_types(data, direction=0)
	resp = make_response(json_lib.dumps(data), status)
	resp.mimetype = "application/json"
	return resp


class EmptyApp(Flask):
	"""
	Rest service app template. Auto register errors, auto "Access-Control-Allow-Origin" header.

	You can put JSON-Schemas to ./json_schemas/*.schema and
	they will be loaded to self.schemas dict (access by file name without suffix).
	"""

	def __init__(self, root_path, app_root, debug=False, extended_errors=True):
		"""

		:param root_path: Path to work dir
		:param app_root: HTTP prefix
		:param debug: Enable Flask debug option
		:param extended_errors: Return exception data with standard HTTP exceptions
		"""
		super().__init__(__name__)
		self.debug = debug
		self.root_path = root_path
		# self.config["APPLICATION_ROOT"] = app_root

		def simple(env, resp):
			resp('404 Page not found', [('Content-Type', 'text/plain')])
			return ['No server for this url']

		self.wsgi_app = DispatcherMiddleware(simple, {app_root: self.wsgi_app})

		self.schemas = {}  # type: Dict[str, Dict]
		path = Path(root_path) / 'json_schemas'
		if path.exists():
			for p in path.iterdir():
				if p.is_file():
					with open(str(p)) as f:
						self.schemas[p.stem] = json_lib.load(f)

		register_errors(self, catalog.values(), debug=extended_errors)

		@self.after_request
		def after(response):
			response.headers["Access-Control-Allow-Origin"] = '*'
			return response

	@staticmethod
	def _options(*args):
		response = make_response()
		response.headers['Access-Control-Allow-Origin'] = '*'
		response.headers['Access-Control-Allow-Methods'] = 'POST, GET, PUT, DELETE, OPTIONS'
		response.headers['Access-Control-Max-Age'] = 1000
		response.headers['Access-Control-Allow-Headers'] = 'origin, x-csrftoken, content-type, accept'
		return response

	def register_crossdomain(self, *rules):
		for rule in rules:
			self.add_url_rule(rule, endpoint=rule + "_options", view_func=self._options, methods=["OPTIONS"])
