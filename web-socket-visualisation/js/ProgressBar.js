"use strict";

var _createClass = function () { function defineProperties(target, props) { for (var i = 0; i < props.length; i++) { var descriptor = props[i]; descriptor.enumerable = descriptor.enumerable || false; descriptor.configurable = true; if ("value" in descriptor) descriptor.writable = true; Object.defineProperty(target, descriptor.key, descriptor); } } return function (Constructor, protoProps, staticProps) { if (protoProps) defineProperties(Constructor.prototype, protoProps); if (staticProps) defineProperties(Constructor, staticProps); return Constructor; }; }();

function _classCallCheck(instance, Constructor) { if (!(instance instanceof Constructor)) { throw new TypeError("Cannot call a class as a function"); } }

var ProgressBar = function () {
    var ProgressBar = function () {
        function ProgressBar(name, max) {
            var formatFunction = arguments.length > 2 && arguments[2] !== undefined ? arguments[2] : null;
            var withPanel = arguments.length > 3 && arguments[3] !== undefined ? arguments[3] : true;

            _classCallCheck(this, ProgressBar);

            if (withPanel) {
                this.body = ProgressBar._pattern.clone();
            } else {
                this.body = ProgressBar._pattern.find('.progress').clone();
            }
            if (name !== null && withPanel) this.body.find("._name").text(name);else this.body.find("._name").hide();
            this.timer = null;
            if (formatFunction !== null) this.formatFunction = formatFunction;else this.formatFunction = function (v, max) {
                return v;
            };
            this.isRunning = false;
            this.setValue(0);
            this.setMax(max);
        }

        _createClass(ProgressBar, [{
            key: "setMax",
            value: function setMax(val) {
                this._max = val;
                this.body.find(".progress-bar").attr("aria-valuemax", val);
                this.setValue(this._val);
            }
        }, {
            key: "setValue",
            value: function setValue(val) {
                var autoRun = arguments.length > 1 && arguments[1] !== undefined ? arguments[1] : true;

                this._val = val;
                this.body.find(".progress-bar").attr("aria-valuenow", val).css("width", val / this._max * 100 + "%").find("._current").text(this.formatFunction(val, this._max));
                if (autoRun) {
                    this.startTimer();
                }
            }
        }, {
            key: "startTimer",
            value: function startTimer() {
                var _this = this;

                if (!this.isRunning) {
                    this.timer = setInterval(function () {
                        var v = _this._val + ProgressBar.delta;
                        if (v <= _this._max) _this.setValue(v);else _this.stopTimer();
                    }, ProgressBar.delta);
                    this.isRunning = true;
                }
                return this.timer;
            }
        }, {
            key: "stopTimer",
            value: function stopTimer() {
                this.isRunning = false;
                clearInterval(this.timer);
            }
        }]);

        return ProgressBar;
    }();

    var pattern = "\n        <div class=\"progress-container panel panel-default\">\n            <div class=\"panel-body\">\n                <h5 class=\"_name\"></h5>\n                <div class=\"progress\">\n                    <div class=\"progress-bar\" role=\"progressbar\" aria-valuenow=\"0\" aria-valuemin=\"0\"\n                         aria-valuemax=\"0\" style=\"min-width: 2em; width: 0; transition: width .2s ease\">\n                        <span class=\"_current\">0</span><span class=\"_suffix\"></span>\n                    </div>\n                </div>\n            </div>\n        </div>\n    ";
    ProgressBar._pattern = $(pattern);
    ProgressBar.delta = 200;
    return ProgressBar;
}();

//# sourceMappingURL=ProgressBar.js.map