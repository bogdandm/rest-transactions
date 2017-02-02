from datetime import timedelta
from functools import update_wrapper
from typing import Callable, Any

from flask import Response
from flask import make_response, request, current_app
from jsonschema import ValidationError
from jsonschema import validate as validjson

import tools.exceptions
from tools import dfilter
from tools.flask_ import request_data, jsonify


def nocache(f: Callable[[], Any]):
	"""Decorator (after). Add headers to disable cache."""

	def wrapper(*args, **kwargs):
		response = f(*args, **kwargs)  # type: Response
		if not isinstance(response, Response):
			response = make_response(response)

		response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
		response.headers["Pragma"] = "no-cache"
		response.headers["Expires"] = "0"
		return response

	wrapper.__name__ = f.__name__
	return wrapper


def validate(schema: dict = None):
	"""
	Decorator factory (before)
	Validate data (including GET data) by JSON-Schema. If data is valid then pass it to route function as dict.

	>>> schema = {...}
	... @app.route("/", methods=["POST"])
	... @validate(schema)
	... def test(data):
	... 	return "Hello " + data["name"]

	:param schema: JSON-Schema
	:return:
	"""

	def decorator(f: Callable[[], Any]):
		def wrapper(*args, **kwargs):
			data = request_data(request)
			if schema:
				try:
					validjson(data, schema)
				except ValidationError as e:
					raise tools.exceptions.ParamsException(e.message)
			return f(*args, **kwargs, data=data)

		wrapper.__name__ = f.__name__
		return wrapper

	return decorator


def json(id_field=None, hide_id=False, add_uri=True):
	"""
	Decorator factory (after)
	Convert returned JSON value to str.
	Return formats:
	* status, json - convert JSON to str
	* json - set status to 200
	* Response - don't do anything, just return raw Response
	* <make_response() args> - don't do anything, just call make_response

	Add "uri" value to json data if add_uri is True. If id_field is given uri == <base_url>/<id>.
	If hide_id is True id_field will removed from json data.

	:param id_field:
	:param hide_id:
	:return:
	"""

	def decorator(f: Callable[[], Any]):
		def wrapper(*args, **kwargs):
			res = f(*args, **kwargs)
			if type(res) is tuple and len(res) == 2 and type(res[1]) is dict:
				status, data = res
			elif type(res) is dict:
				status, data = 200, res
			elif type(res) is Response:
				return res
			else:
				return make_response(res)
			if "uri" not in data:
				uri = request.base_url
				if id_field is not None:
					uri += "/" + data.get(id_field)
					if hide_id:
						data = dfilter(data, id_field, reverse=True)
				data["uri"] = uri
			return jsonify(status, data, True)

		wrapper.__name__ = f.__name__
		return wrapper

	return decorator


def crossdomain(origin=None, methods=None, headers=None,
				max_age=21600, attach_to_all=True,
				automatic_options=True):
	if methods is not None:
		methods = ', '.join(sorted(x.upper() for x in methods))
	if headers is not None and not isinstance(headers, str):
		headers = ', '.join(x.upper() for x in headers)
	if not isinstance(origin, str):
		origin = ', '.join(origin)
	if isinstance(max_age, timedelta):
		max_age = max_age.total_seconds()

	def get_methods():
		if methods is not None:
			return methods

		options_resp = current_app.make_default_options_response()
		return options_resp.headers['allow']

	def decorator(f: Callable[[], Any]):
		def wrapped_function(*args, **kwargs):
			if automatic_options and request.method == 'OPTIONS':
				resp = current_app.make_default_options_response()
			else:
				resp = make_response(f(*args, **kwargs))
			if not attach_to_all and request.method != 'OPTIONS':
				return resp

			h = resp.headers

			h['Access-Control-Allow-Origin'] = origin
			h['Access-Control-Allow-Methods'] = get_methods()
			h['Access-Control-Max-Age'] = str(max_age)
			if headers is not None:
				h['Access-Control-Allow-Headers'] = headers
			return resp

		f.provide_automatic_options = False
		return update_wrapper(wrapped_function, f)

	return decorator


if __name__ == '__main__':
	from flask import Flask

	app = Flask(__name__)
	schema = {
		"$schema": "http://json-schema.org/draft-04/schema#",
		"type": "object",
		"properties": {
			"x": {
				"type": "string"
			}
		},
		"required": [
			"x"
		]
	}


	@app.route("/", methods=["POST"])
	@validate(schema)
	@json()
	def test(data):
		return {"OK": "X is %s" % data['x']}


	app.run()
