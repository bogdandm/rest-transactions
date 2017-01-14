"use strict";

const TransactionGenerator = (function () {
    return class TransactionGenerator {
        constructor() {
            this.globalTimeout = 0;
            this.numberOfServices = 0;
            this.localTimeout = [0, 0];
            this.params_node = null;
            this.json_node = null;
            this._json = null;
        }

        connect(params_node, json_node) {
            this.params_node = params_node;
            this.json_node = json_node;

            this.params_node.find("#i_gt").val(localStorage.getItem("generator_globalTimeout")).on("input", (e) => {
                this.globalTimeout = Number($(e.target).val());
                localStorage.setItem("generator_globalTimeout", this.globalTimeout);
                this.render();
            });
            this.params_node.find("#i_ns").val(localStorage.getItem("generator_numberOfServices")).on("input", (e) => {
                this.numberOfServices = Number($(e.target).val());
                localStorage.setItem("generator_numberOfServices", this.numberOfServices);
                this.render();
            });
            this.params_node.find("#i_lt0").val(localStorage.getItem("generator_localTimeout0")).on("input", (e) => {
                this.localTimeout[0] = Number($(e.target).val());
                localStorage.setItem("generator_localTimeout0", this.localTimeout[0]);
                this.render();
            });
            this.params_node.find("#i_lt1").val(localStorage.getItem("generator_localTimeout1")).on("input", (e) => {
                this.localTimeout[1] = Number($(e.target).val());
                localStorage.setItem("generator_localTimeout1", this.localTimeout[1]);
                this.render();
            });
        }

        static *actionGenerator(number, localTimeout) {
            for (let i = 0; i < number; i++) {
                yield TransactionGenerator.getAction(i, localTimeout)
            }
        }

        static getAction(i, localTimeout) {
            let rndWord = choice(globals.words);
            return {
                _id: `Service #${i} GET ${rndWord}`,
                service: {
                    //name: `Service #${i}`,
                    url: `http://localhost:501${i}/api`,
                    timeout: randInt(...localTimeout),
                },
                url: "/" + rndWord,
                method: "GET",
                data: {},
                headers: {}
            }
        }

        _toJSON() {
            return {
                timeout: this.globalTimeout,
                actions: [...TransactionGenerator.actionGenerator(this.numberOfServices, this.localTimeout)]
            };
        }

        get json() {
            if (this._json) {
                return this._json
            } else {
                return this._json = this._toJSON()
            }
        }

        render() {
            this._json = null;
            this.json_node.text(JSON.stringify(this.json, null, 4));
        }
    };
})();
