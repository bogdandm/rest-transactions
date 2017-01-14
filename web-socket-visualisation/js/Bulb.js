"use strict";

var _createClass = function () { function defineProperties(target, props) { for (var i = 0; i < props.length; i++) { var descriptor = props[i]; descriptor.enumerable = descriptor.enumerable || false; descriptor.configurable = true; if ("value" in descriptor) descriptor.writable = true; Object.defineProperty(target, descriptor.key, descriptor); } } return function (Constructor, protoProps, staticProps) { if (protoProps) defineProperties(Constructor.prototype, protoProps); if (staticProps) defineProperties(Constructor, staticProps); return Constructor; }; }();

function _defineProperty(obj, key, value) { if (key in obj) { Object.defineProperty(obj, key, { value: value, enumerable: true, configurable: true, writable: true }); } else { obj[key] = value; } return obj; }

function _classCallCheck(instance, Constructor) { if (!(instance instanceof Constructor)) { throw new TypeError("Cannot call a class as a function"); } }

var Bulb = function () {
    var Bulb = function () {
        function Bulb(color_off) {
            var color_on = arguments.length > 1 && arguments[1] !== undefined ? arguments[1] : null;
            var duration = arguments.length > 2 && arguments[2] !== undefined ? arguments[2] : 0.5;

            var _m;

            var size = arguments.length > 3 && arguments[3] !== undefined ? arguments[3] : 6;
            var border = arguments.length > 4 && arguments[4] !== undefined ? arguments[4] : null;

            _classCallCheck(this, Bulb);

            if (Bulb[color_off]) color_off = Bulb[color_off][0];
            if (Bulb[color_on]) color_on = Bulb[color_on][1];
            var m = (_m = {}, _defineProperty(_m, 1, "fade-out-1s"), _defineProperty(_m, 0.5, "fade-out-05s"), _defineProperty(_m, 0.25, "fade-out-025s"), _m);
            this.duration = duration * 1000;
            this.class = m[duration];
            this.body = Bulb.pattern.clone();
            this.body.css({
                "background-color": "rgba(" + color_off + ",1)"
            }).height(size).width(size).find(".flash").css("background", "radial-gradient(ellipse at center,\n                    rgba(" + color_on + ", 1) 0%,\n                    rgba(" + color_on + ", 0.8) 2%,\n                    rgba(255, 255, 255, 0) 40%\n                )");

            switch (border) {
                case "black":
                    this.body.css("box-shadow", "0px 0px 0px 1px #101010");
                    break;

                default:
                    this.body.css("box-shadow", "0px 0px 0px 1px " + border);
                    break;
            }

            this.timeout = null;
            this.timer = null;
        }

        _createClass(Bulb, [{
            key: "blink",
            value: function blink() {
                var _this = this;

                clearTimeout(this.timeout);
                this.body.find('.flash').removeClass(this.class);
                this.timeout = setTimeout(function () {
                    return _this.body.find('.flash').addClass(_this.class);
                }, 32);
            }
        }, {
            key: "turn",
            value: function turn(val) {
                if (val === undefined) val = true;
                var flash = this.body.find('.flash');
                clearInterval(this.timer);
                clearTimeout(this.timeout);
                if (val) {
                    flash.removeClass(this.class).css("opacity", 1);
                } else {
                    flash.css("opacity", "").addClass(this.class);
                }
            }
        }, {
            key: "turn_blink",
            value: function turn_blink(val) {
                var _this2 = this;

                if (val === undefined) {
                    val = this.duration;
                }
                clearInterval(this.timer);
                if (val) {
                    this.timer = setInterval(function () {
                        return _this2.blink();
                    }, val);
                }
            }
        }]);

        return Bulb;
    }();

    var pattern = "\n        <div class=\"bulb\">\n            <div class=\"flash fade-out-05s\"></div>\n        </div>\n    ";

    Bulb.pattern = $(pattern);
    Bulb.green = ["0,126,51", "0,200,81"];
    Bulb.red = ["204,0,0", "255,68,68"];
    Bulb.blue = ["0,153,204", "51,181,229"];
    return Bulb;
}();

//# sourceMappingURL=Bulb.js.map