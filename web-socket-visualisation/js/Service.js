"use strict";

var _createClass = function () { function defineProperties(target, props) { for (var i = 0; i < props.length; i++) { var descriptor = props[i]; descriptor.enumerable = descriptor.enumerable || false; descriptor.configurable = true; if ("value" in descriptor) descriptor.writable = true; Object.defineProperty(target, descriptor.key, descriptor); } } return function (Constructor, protoProps, staticProps) { if (protoProps) defineProperties(Constructor.prototype, protoProps); if (staticProps) defineProperties(Constructor, staticProps); return Constructor; }; }();

function _toConsumableArray(arr) { if (Array.isArray(arr)) { for (var i = 0, arr2 = Array(arr.length); i < arr.length; i++) { arr2[i] = arr[i]; } return arr2; } else { return Array.from(arr); } }

function _classCallCheck(instance, Constructor) { if (!(instance instanceof Constructor)) { throw new TypeError("Cannot call a class as a function"); } }

var Service = function () {
    var Service = function () {
        function Service(name, timeout_local, sse) {
            _classCallCheck(this, Service);

            this.name = name;

            this.body = Service._pattern.clone();
            this.cbody = Service._controller_pattern.clone();
            this.body.find("._name").text(name);
            this.cbody.find("._name").text(name);

            this.bulb_ugly = new (Function.prototype.bind.apply(Bulb, [null].concat(_toConsumableArray(Bulb.blue), [0.5, 10])))();
            this.body.find('._bulbs').append(this.bulb_ugly.body);
            this.bulb_good = new (Function.prototype.bind.apply(Bulb, [null].concat(_toConsumableArray(Bulb.green), [0.5, 10])))();
            this.body.find('._bulbs').append(this.bulb_good.body);
            this.bulb_bad = new (Function.prototype.bind.apply(Bulb, [null].concat(_toConsumableArray(Bulb.red), [0.5, 10])))();
            this.body.find('._bulbs').append(this.bulb_bad.body);

            this.cbulb_ugly = new (Function.prototype.bind.apply(Bulb, [null].concat(_toConsumableArray(Bulb.blue), [0.5, 10])))();
            this.cbody.find('._bulbs').append(this.cbulb_ugly.body);
            this.cbulb_good = new (Function.prototype.bind.apply(Bulb, [null].concat(_toConsumableArray(Bulb.green), [0.5, 10])))();
            this.cbody.find('._bulbs').append(this.cbulb_good.body);
            this.cbulb_bad = new (Function.prototype.bind.apply(Bulb, [null].concat(_toConsumableArray(Bulb.red), [0.5, 10])))();
            this.cbody.find('._bulbs').append(this.cbulb_bad.body);

            this.c_local_timeout = new ProgressBar(null, timeout_local, function (v, max) {
                return formatTime(v, "s");
            }, false);
            this.cbody.find("._bars").append(this.c_local_timeout.body);
            this.c_local_timeout.startTimer();

            this.sse_listener = new EventListener(sse, this);
        }

        _createClass(Service, [{
            key: "init_timeouts",
            value: function init_timeouts(timeout_ping, timeout_work) {
                this.timeout_ping = new ProgressBar("Ping timeout", timeout_ping, function (v, max) {
                    return formatTime(v, max > 2000 ? "s" : "ms");
                });
                this.body.find("._bars").append(this.timeout_ping.body);
                this.timeout_ping.startTimer();

                this.timeout_work = new ProgressBar("Work timeout", timeout_work, function (v, max) {
                    return formatTime(v, "s");
                });
                this.body.find("._bars").append(this.timeout_work.body);
            }
        }, {
            key: "setStatus",
            value: function setStatus(status) {
                var _this = this;

                var panel = this.body.find(".panel");

                (function () {
                    switch (status) {
                        case "open_connection":
                            _this.bulb_ugly.turn_blink(false);
                            _this.bulb_good.turn_blink(false);
                            _this.bulb_bad.turn_blink(false);
                            panel.replaceClass("panel-", "panel-default");
                            break;

                        case "lost_connection":
                            var duration = 1500;
                            setTimeout(function () {
                                return _this.bulb_ugly.turn_blink(duration);
                            }, 0);
                            setTimeout(function () {
                                return _this.bulb_good.turn_blink(duration);
                            }, duration / 3);
                            setTimeout(function () {
                                return _this.bulb_bad.turn_blink(duration);
                            }, 2 * duration / 3);
                            panel.replaceClass("panel-", "panel-warning");
                            break;

                        case "ready_commit":
                            panel.replaceClass("panel-", "panel-info");
                            _this.bulb_good.turn();
                            break;

                        case "fail":
                            panel.replaceClass("panel-", "panel-danger");
                            _this.timeout_work.stopTimer();
                            _this.timeout_ping.stopTimer();
                            _this.bulb_good.turn(false);
                            _this.bulb_bad.turn();
                            break;

                        case "commit":
                            panel.replaceClass("panel-", "panel-primary");
                            _this.bulb_good.turn_blink();
                            break;

                        case "done":
                            panel.replaceClass("panel-", "panel-success");
                            _this.timeout_work.stopTimer();
                            break;

                        case "finish":
                            _this.timeout_ping.stopTimer();
                            _this.bulb_ugly.turn();
                            _this.bulb_good.turn();
                            break;

                        case "rollback":
                            panel.replaceClass("panel-", "panel-danger");
                            _this.timeout_work.stopTimer();
                            _this.timeout_ping.stopTimer();
                            _this.bulb_ugly.turn();
                            _this.bulb_good.turn(false);
                            _this.bulb_bad.turn();
                            break;

                        default:
                            panel.replaceClass("panel-", "panel-default");
                            break;
                    }
                })();
            }
        }, {
            key: "setCStatus",
            value: function setCStatus(status) {
                var panel = this.cbody;
                switch (status) {
                    case "ready_commit":
                        panel.replaceClass("panel-", "panel-info");
                        this.c_local_timeout.stopTimer();
                        this.cbulb_good.turn();
                        break;

                    case "fail":
                        panel.replaceClass("panel-", "panel-danger");
                        this.c_local_timeout.stopTimer();
                        this.cbulb_good.turn(false);
                        this.cbulb_bad.turn();
                        break;

                    case "commit":
                        panel.replaceClass("panel-", "panel-info");
                        this.cbulb_good.turn_blink();
                        break;

                    case "done":
                        panel.replaceClass("panel-", "panel-success");
                        this.cbulb_ugly.turn();
                        this.cbulb_good.turn();
                        break;

                    case "rollback":
                        panel.replaceClass("panel-", "panel-danger");
                        this.c_local_timeout.stopTimer();
                        this.cbulb_ugly.turn();
                        this.cbulb_good.turn(false);
                        this.cbulb_bad.turn();
                        break;

                    default:
                        panel.replaceClass("panel-", "panel-default");
                        break;
                }
            }
        }, {
            key: "event",
            value: function event(_event) {
                switch (_event.type) {
                    case "ready_commit":
                    case "fail":
                    case "commit":
                    case "done":
                    case "finish":
                    case "rollback":
                        this.setStatus(_event.type);
                        break;

                    case "init":
                        this.init_timeouts(_event.data["ping_timeout"] * 2, _event.data["result_timeout"]);
                        this.bulb_ugly.blink();
                        this.bulb_good.blink();
                        this.bulb_bad.blink();
                        break;

                    case "wait_ping":
                        this.timeout_ping.setValue(0);
                        if (!this.timeout_ping.isRunning) this.timeout_ping.startTimer();
                        break;

                    case "ping":
                        this.bulb_ugly.blink();
                        break;

                    case "touch":
                        this.bulb_good.blink();
                        this.timeout_work.startTimer();
                        break;

                    default:
                        console.warn("Unhandled event", _event);
                }
            }
        }]);

        return Service;
    }();

    var service_pattern = "\n        <div class=\"service container col-md-3\">\n            <div class=\"panel panel-default\">\n                <div class=\"panel-heading flex-h\">\n                    <span class=\"_name\"></span>\n                    <div class=\"_bulbs flex-h\"></div>\n                </div>\n                <div class=\"panel-body\">\n                    <div class=\"_bars panel-group\">\n                        <!-- Progress bars -->\n                    </div>                \n                </div>\n            </div>\n        </div>\n    ";

    var controller_pattern = "\n        <div class=\"controller-service panel panel-default\">        \n            <div class=\"panel-heading flex-h\">\n                <span class=\"_name\"></span>\n                <div class=\"_bulbs flex-h\"></div>\n            </div>\n            <div class=\"panel-body panel-group _bars\">\n                <!-- Progress bars -->\n            </div>\n        </div>\n    ";
    Service._pattern = $(service_pattern);
    Service._controller_pattern = $(controller_pattern);
    return Service;
}();

//# sourceMappingURL=Service.js.map