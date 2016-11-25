from tools.flask_ import EmptyApp

from tools.flask_.decorators import validate, json


class ControllerRestService(EmptyApp):
	VERSION = "v.alpha"

	def __init__(self, root_path, app_root="/controller/api/%s" % VERSION):
		super().__init__(root_path, app_root)

		@self.route("/transaction", methods=["POST"])
		@validate(self.schemas["transaction.schema"])
		@json
		def r_transaction_post(data):
			pass

		@self.route("/transaction/<trid>", methods=["GET"])
		@json
		def r_transaction_get(trid):
			pass

		@self.route("/transaction/<trid>", methods=["DELETE"])
		@json
		def r_transaction_get(trid):
			pass

		@self.route("/transaction/<trid>", methods=["POST"])
		@validate(self.schemas["service_status_callback.schema"])
		@json
		def r_transaction_get(data, trid):
			pass
