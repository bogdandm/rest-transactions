"use strict";

const Service = (function () {
    let Service = class {
        constructor(name, timeout_local, sse) {
            this.name = name;

            this.body = Service._pattern.clone();
            this.cbody = Service._controller_pattern.clone();
            this.body.find("._name").text(name);
            this.cbody.find("._name").text(name);

            this.bulb_ugly = new Bulb(...Bulb.blue, 0.5, 10);
            this.body.find('._bulbs').append(this.bulb_ugly.body);
            this.bulb_good = new Bulb(...Bulb.green, 0.5, 10);
            this.body.find('._bulbs').append(this.bulb_good.body);
            this.bulb_bad = new Bulb(...Bulb.red, 0.5, 10);
            this.body.find('._bulbs').append(this.bulb_bad.body);

            this.cbulb_ugly = new Bulb(...Bulb.blue, 0.5, 10);
            this.cbody.find('._bulbs').append(this.cbulb_ugly.body);
            this.cbulb_good = new Bulb(...Bulb.green, 0.5, 10);
            this.cbody.find('._bulbs').append(this.cbulb_good.body);
            this.cbulb_bad = new Bulb(...Bulb.red, 0.5, 10);
            this.cbody.find('._bulbs').append(this.cbulb_bad.body);

            this.c_local_ping = new ProgressBar(null, timeout_local, (v) => formatTime(v, "s"), false);
            this.cbody.find("._bars").append(this.c_local_ping.body);
            this.c_local_ping.startTimer();

            this.sse_listener = new EventListener(sse, this);
        }

        init_timeouts(timeout_ping, timeout_work) {
            this.timeout_ping = new ProgressBar("Ping timeout", timeout_ping, (v) => formatTime(v, "s"));
            this.body.find("._bars").append(this.timeout_ping.body);
            this.timeout_ping.startTimer();

            this.timeout_work = new ProgressBar("Work timeout", timeout_work, (v) => formatTime(v, "s"));
            this.body.find("._bars").append(this.timeout_work.body);
        }

        setStatus(status) {
            let panel = this.body.find(".panel");
            switch (status) {
                case "open_connection":
                    this.bulb_ugly.turn_blink(false);
                    this.bulb_good.turn_blink(false);
                    this.bulb_bad.turn_blink(false);
                    panel.replaceClass("panel-", "panel-default");
                    break;

                case "lost_connection":
                    const duration = 1500;
                    setTimeout(() => this.bulb_ugly.turn_blink(duration), 0);
                    setTimeout(() => this.bulb_good.turn_blink(duration), duration / 3);
                    setTimeout(() => this.bulb_bad.turn_blink(duration), 2 * duration / 3);
                    panel.replaceClass("panel-", "panel-danger");
                    break;

                case "ready_commit":
                    panel.replaceClass("panel-", "panel-success");
                    this.bulb_good.turn(true);
                    break;

                case "fail":
                    panel.replaceClass("panel-", "panel-danger");
                    this.bulb_bad.turn(true);
                    break;

                default:
                    panel.replaceClass("panel-", "panel-primary");
                    break;
            }
        }

        setCStatus(status) {
            let panel = this.cbody;
            switch (status) {
                case "ready_commit":
                    panel.replaceClass("panel-", "panel-info");
                    this.cbulb_good.turn();
                    break;

                case "fail":
                    panel.replaceClass("panel-", "panel-danger");
                    this.cbulb_good.turn(false);
                    this.cbulb_bad.turn();
                    break;

                case "prepare_commit":
                    panel.replaceClass("panel-", "panel-info");
                    this.cbulb_good.turn_blink();
                    break;

                case "committed":
                    panel.replaceClass("panel-", "panel-success");
                    this.cbulb_ugly.turn();
                    this.cbulb_good.turn();
                    break;

                case "rollback":
                    panel.replaceClass("panel-", "panel-danger");
                    this.cbulb_ugly.turn();
                    this.cbulb_good.turn(false);
                    this.cbulb_bad.turn();
                    break;

                default:
                    panel.replaceClass("panel-", "panel-default");
                    break;
            }
        }

        event(event) {
            switch (event.type) {
                case "init":
                    this.init_timeouts(event.data["ping_timeout"] * 2, event.data["result_timeout"]);
                    this.bulb_ugly.blink();
                    this.bulb_good.blink();
                    this.bulb_bad.blink();
                    break;

                case "fail":
                    this.setStatus("fail");
                    this.timeout_work.stopTimer();
                    this.timeout_ping.stopTimer();
                    break;

                case "wait_ping":
                    this.timeout_ping.setValue(0);
                    if (!this.timeout_ping.isRunning)
                        this.timeout_ping.startTimer();
                    break;

                case "ping":
                    this.bulb_ugly.blink();
                    break;

                case "ready_commit":
                    this.setStatus("ready_commit");
                    this.timeout_work.stopTimer();
                    break;

                case "rollback":
                    this.bulb_bad.turn(true);
                    this.timeout_work.stopTimer();
                    this.timeout_ping.stopTimer();
                    break;

                case "commit":
                    this.bulb_good.turn(true);
                    this.timeout_work.stopTimer();
                    this.timeout_ping.stopTimer();
                    break;

                case "touch":
                    this.bulb_good.blink();
                    this.timeout_work.startTimer();
                    break;

                default:
                    console.warn("Unhandled event")
            }
        }
    };

    let service_pattern = `
        <div class="service container col-md-3">
            <div class="panel panel-default">
                <div class="panel-heading flex-h">
                    <span class="_name"></span>
                    <div class="_bulbs flex-h"></div>
                </div>
                <div class="panel-body">
                    <div class="_bars panel-group">
                        <!-- Progress bars -->
                    </div>                
                </div>
            </div>
        </div>
    `;

    let controller_pattern = `
        <div class="controller-service panel panel-default">        
            <div class="panel-heading flex-h">
                <span class="_name"></span>
                <div class="_bulbs flex-h"></div>
            </div>
            <div class="panel-body panel-group _bars">
                <!-- Progress bars -->
            </div>
        </div>
    `;
    Service._pattern = $(service_pattern);
    Service._controller_pattern = $(controller_pattern);
    return Service;
})();
