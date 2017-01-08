const Bulb = (function () {
    let Bulb = class {
        constructor(color_off, color_on = null, duration = 0.5, size = 6, border = null) {
            if (Bulb[color_off])
                color_off = Bulb[color_off][0];
            if (Bulb[color_on])
                color_on = Bulb[color_on][1];
            let m = {
                [1]: "fade-out-1s",
                [0.5]: "fade-out-05s",
                [0.25]: "fade-out-025s"
            };
            this.duration = duration * 1000;
            this.class = m[duration];
            this.body = Bulb.pattern.clone();
            this.body
                .css({
                    "background-color": `rgba(${color_off},1)`
                })
                .height(size).width(size)
                .find(".flash").css("background", `radial-gradient(ellipse at center,
                    rgba(${color_on}, 1) 0%,
                    rgba(${color_on}, 0.8) 2%,
                    rgba(255, 255, 255, 0) 40%
                )`);

            switch (border) {
                case "black":
                    this.body.css("box-shadow", `0px 0px 0px 1px #101010`);
                    break;

                default:
                    this.body.css("box-shadow", `0px 0px 0px 1px ${border}`);
                    break;
            }

            this.timeout = null;
            this.timer = null;
        }

        blink() {
            clearTimeout(this.timeout);
            this.body.find('.flash').removeClass(this.class);
            this.timeout = setTimeout(() => this.body.find('.flash').addClass(this.class), 32);
        }

        turn(val) {
            if (val === undefined) val = true;
            let flash = this.body.find('.flash');
            clearInterval(this.timer);
            clearTimeout(this.timeout);
            if (val) {
                flash.removeClass(this.class).css("opacity", 1);
            } else {
                flash.css("opacity", "").addClass(this.class);
            }
        }

        turn_blink(val) {
            if (val === undefined) {
                val = this.duration
            }
            clearInterval(this.timer);
            if (val) {
                this.timer = setInterval(() => this.blink(), val)
            }
        }
    };

    let pattern = `
        <div class="bulb">
            <div class="flash fade-out-05s"></div>
        </div>
    `;

    Bulb.pattern = $(pattern);
    Bulb.green = ["0,126,51", "0,200,81"];
    Bulb.red = ["204,0,0", "255,68,68"];
    Bulb.blue = ["0,153,204", "51,181,229"];
    return Bulb;
})();