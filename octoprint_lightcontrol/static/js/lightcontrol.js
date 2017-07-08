$(function() {
    function LightControlViewModel(parameters) {
        var self = this;

        self.global_settings = parameters[0];
        self.settings = undefined;
        self.loginState = parameters[1];
        self.isLightOn = ko.observable(undefined);
        self.light_indicator = undefined;

        self.onAfterBinding = function() {
            self.settings = self.global_settings.settings.plugins.lightcontrol;

            self.light_indicator = $("#lightcontrol_indicator");
        };

        self.onDataUpdaterPluginMessage = function(plugin, data) {
            if (plugin != "lightcontrol") {
                return;
            }

            self.isLightOn(data.isLightOn);

            if (self.isLightOn()) {
                self.light_indicator.css('color', '#FFFF00');
            } else {
                self.light_indicator.css('color', '#808080');
            }

        };

        self.toggleLight = function() {
            if (self.isLightOn()) {
                self.turnLightOff();
            } else {
                self.turnLightOn();
            }
        };

        self.turnLightOn = function() {
            $.ajax({
                url: API_BASEURL + "plugin/lightcontrol",
                type: "POST",
                dataType: "json",
                data: JSON.stringify({
                    command: "turnLightOn"
                }),
                contentType: "application/json; charset=UTF-8"
            })
        };

    	self.turnLightOff = function() {
            $.ajax({
                url: API_BASEURL + "plugin/lightcontrol",
                type: "POST",
                dataType: "json",
                data: JSON.stringify({
                    command: "turnLightOff"
                }),
                contentType: "application/json; charset=UTF-8"
            })
        };   
    }

    ADDITIONAL_VIEWMODELS.push([
        LightControlViewModel,
        ["settingsViewModel", "loginStateViewModel"],
        ["#navbar_plugin_lightcontrol"]
    ]);
});
