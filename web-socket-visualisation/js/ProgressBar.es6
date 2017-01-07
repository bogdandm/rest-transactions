"use strict";

const ProgressBar = (function () {
    let ProgressBar = class {
        constructor(name, max, formatFunction = null, withPanel = true) {
            if (withPanel) {
                this.body = ProgressBar._pattern.clone();
            } else {
                this.body = ProgressBar._pattern.find('.progress').clone();
            }
            if (name !== null && withPanel)
                this.body.find("._name").text(name);
            else
                this.body.find("._name").hide();
            this.timer = null;
            if (formatFunction !== null)
                this.formatFunction = formatFunction;
            else
                this.formatFunction = v => v;
            this.isRunning = false;
            this.setValue(0);
            this.setMax(max);
        }

        setMax(val) {
            this._max = val;
            this.body.find(".progress-bar").attr("aria-valuemax", val);
            this.setValue(this._val)
        }

        setValue(val, autoRun = true) {
            this._val = val;
            this.body.find(".progress-bar").attr("aria-valuenow", val).css("width", val / this._max * 100 + "%")
                .find("._current").text(this.formatFunction(val));
            if (autoRun) {
                this.startTimer();
            }
        }

        startTimer() {
            if (!this.isRunning) {
                this.timer = setInterval(() => {
                    let v = this._val + ProgressBar.delta;
                    if (v <= this._max)
                        this.setValue(v);
                    else
                        this.stopTimer()
                }, ProgressBar.delta);
                this.isRunning = true;
            }
            return this.timer;
        }

        stopTimer() {
            this.isRunning = false;
            clearInterval(this.timer);
        }
    };

    let pattern = `
        <div class="progress-container panel panel-default">
            <div class="panel-body">
                <h5 class="_name"></h5>
                <div class="progress">
                    <div class="progress-bar" role="progressbar" aria-valuenow="0" aria-valuemin="0"
                         aria-valuemax="0" style="min-width: 2em; width: 0; transition: width .2s ease">
                        <span class="_current">0</span><span class="_suffix"></span>
                    </div>
                </div>
            </div>
        </div>
    `;
    ProgressBar._pattern = $(pattern);
    ProgressBar.delta = 200;
    return ProgressBar;
})();
