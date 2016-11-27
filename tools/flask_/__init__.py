import json as json_lib
from pathlib import Path
from typing import Union

from flask import Flask
from flask import Response, Request
from flask import make_response
from werkzeug.wsgi import DispatcherMiddleware

from tools import transform_json_types
from tools.exceptions import catalog


def register_errors(app, http_errors: dict, custom_errors: dict):
	# HTTP
	def error_handler_factory(error_, data_):
		def func1(e):
			return jsonify(data_["code"], data_)

		func1.__name__ = "error" + error_
		return func1

	for error, e_data in http_errors.items():
		app.register_error_handler(e_data["code"], error_handler_factory(error, e_data))

	# Custom
	def func(e):
		return jsonify(e.code, {
			"code": e.n,
			"description": e.desc,
			"data": e.data
		})

	for e_name, error in custom_errors.items():
		app.register_error_handler(error, func)


def request_data(request_: Request):
	if request_.method in ("GET", "DELETE"):
		return request_.args

	if request_.is_json:
		return request_.get_json()
	return request_.form


def dejsonify(data: str, need_transform=False) -> Union[dict, list]:
	data = json_lib.loads(data)
	if need_transform:
		transform_json_types(data, direction=1)
	return data


def jsonify(status: int, data: Union[dict, list], need_transform=False) -> Response:
	if need_transform:
		transform_json_types(data, direction=0)
	resp = make_response(json_lib.dumps(data))
	resp.status_code = status
	resp.mimetype = "application/json"
	return resp


class EmptyApp(Flask):
	def __init__(self, root_path, app_root):
		super().__init__(__name__)
		self.root_path = root_path
		self.config["APPLICATION_ROOT"] = app_root

		def simple(env, resp):
			resp(b'404 Page not found', [(b'Content-Type', b'text/plain')])
			return [b'No server for this url']

		self.wsgi_app = DispatcherMiddleware(simple, {app_root: self.wsgi_app})

		self.schemas = {}
		path = Path('json_schemas')
		if path.exists():
			for p in path.iterdir():
				if p.is_file():
					with open(str(p)) as f:
						self.schemas[p.stem] = json_lib.loads(f.read())

		with open("static/default_errors.json") as f:
			http_errors = json_lib.loads(f.read())

		register_errors(self, http_errors, catalog)

		@self.after_request
		def after(response):
			response.headers["Access-Control-Allow-Origin"] = '*'
			return response
