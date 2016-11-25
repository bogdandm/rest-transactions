import json as json_lib

from flask import Flask

from tools.exceptions import catalog
from tools.flask_ import register_errors
from tools.flask_.decorators import validate_get, json, validate

app = Flask(__name__)

with open("static/default_errors.json") as f:
	http_errors = json_lib.loads(f.read())

register_errors(app, http_errors, catalog)

schema1 = {
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

schema2 = {
	"$schema": "http://json-schema.org/draft-04/schema#",
	"type": "array",
	"items": {
		"type": "integer"
	}
}


@app.route("/sum", methods=["GET"])
@validate_get(schema1)
@json
def index_get(data):
	return {"result": int(data['x']) + int(data['y'])}


@app.route("/sum", methods=["POST"])
@validate(schema2)
@json
def index_post(data):
	return {"result": sum(data)}


app.run()
