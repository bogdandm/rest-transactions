from tools.flask_ import EmptyApp
from tools.flask_.decorators import json, validate

app = EmptyApp("./", "/api")

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
@json
def index_get(data):
	return {"result": int(data['x']) + int(data['y'])}


@app.route("/sum", methods=["POST"])
@validate(schema2)
@json
def index_post(data):
	return {"result": sum(data)}


app.run()
