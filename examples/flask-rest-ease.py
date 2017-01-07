from random import randint

from bson import ObjectId

from tools.flask_ import EmptyApp
from tools.flask_.decorators import json, validate

app = EmptyApp("./", "/api", False, True)

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
@validate(schema1)
@json()
def index_get(data):
	return {"result": int(data['x']) + int(data['y'])}


@app.route("/sum", methods=["POST"])
@validate(schema2)
@json()
def index_post(data):
	return {"result": sum(data)}


@app.route("/random", methods=["POST"])
@json(id_field="_id")
def random_post():
	return {"result": randint(0, 2 ** 100), "_id": str(ObjectId())}


@app.route("/500")
@json()
def test500():
	return 1/0


app.run()
