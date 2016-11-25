from flask import Response, make_response, request
from jsonschema import ValidationError
from jsonschema import validate as validjson

import tools.exceptions
from tools.flask_ import request_data, jsonify


def validate_get(schema: dict):
	def decorator(f):
		def wrapper(*args, **kwargs):
			data = request.args
			if schema:
				try:
					validjson(data, schema)
				except ValidationError as e:
					raise tools.exceptions.ParamsException(e.message)
			return f(*args, **kwargs, data=data)

		wrapper.__name__ = f.__name__
		return wrapper

	return decorator


def validate(schema: dict):
	def decorator(f):
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


def json(f):
	def wrapper(*args, **kwargs):
		res = f(*args, **kwargs)
		if type(res) is tuple:
			status, data = res
			return jsonify(status, data, True)
		elif type(res) is dict:
			return jsonify(200, res, True)
		elif type(res) is Response:
			return res
		else:
			make_response(res)

	wrapper.__name__ = f.__name__
	return wrapper


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
	@json
	@validate(schema)
	def test(data):
		return {"OK": "X is %s" % data['x']}


	app.run()
