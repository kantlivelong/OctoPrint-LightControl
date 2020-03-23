# coding=utf-8
from __future__ import absolute_import

__author__ = "Shawn Bruce <kantlivelong@gmail.com>"
__license__ = "GNU Affero General Public License http://www.gnu.org/licenses/agpl.html"
__copyright__ = "Copyright (C) 2017 Shawn Bruce - Released under terms of the AGPLv3 License"

import octoprint.plugin
from octoprint.server import user_permission
from octoprint.util import RepeatedTimer
import RPi.GPIO as GPIO
import time
import threading
import os
from flask import make_response, jsonify

class LightControl(octoprint.plugin.StartupPlugin,
                   octoprint.plugin.TemplatePlugin,
                   octoprint.plugin.AssetPlugin,
                   octoprint.plugin.SettingsPlugin,
                   octoprint.plugin.SimpleApiPlugin):

    def __init__(self):
        self._pin_to_gpio_rev1 = [-1, -1, -1, 0, -1, 1, -1, 4, 14, -1, 15, 17, 18, 21, -1, 22, 23, -1, 24, 10, -1, 9, 25, 11, 8, -1, 7, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1 ]
        self._pin_to_gpio_rev2 = [-1, -1, -1, 2, -1, 3, -1, 4, 14, -1, 15, 17, 18, 27, -1, 22, 23, -1, 24, 10, -1, 9, 25, 11, 8, -1, 7, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1 ]
        self._pin_to_gpio_rev3 = [-1, -1, -1, 2, -1, 3, -1, 4, 14, -1, 15, 17, 18, 27, -1, 22, 23, -1, 24, 10, -1, 9, 25, 11, 8, -1, 7, -1, -1, 5, -1, 6, 12, 13, -1, 19, 16, 26, 20, -1, 21 ]

        self.GPIOMode = ''
        self.onoffGPIOPin = 0
        self.invertonoffGPIOPin = False
        self.isLightOn = False
        self._checkLightTimer = None
        self._configuredGPIOPins = []

    def on_settings_initialized(self):
        self.GPIOMode = self._settings.get(["GPIOMode"])
        self._logger.debug("GPIOMode: %s" % self.GPIOMode)

        self.switchingMethod = self._settings.get(["switchingMethod"])
        self._logger.debug("switchingMethod: %s" % self.switchingMethod)

        self.onoffGPIOPin = self._settings.get_int(["onoffGPIOPin"])
        self._logger.debug("onoffGPIOPin: %s" % self.onoffGPIOPin)

        self.invertonoffGPIOPin = self._settings.get_boolean(["invertonoffGPIOPin"])
        self._logger.debug("invertonoffGPIOPin: %s" % self.invertonoffGPIOPin)

        self._configure_gpio()

        self._checkLightTimer = RepeatedTimer(5.0, self.check_light_state, None, None, True)
        self._checkLightTimer.start()

    def _gpio_board_to_bcm(self, pin):
        if GPIO.RPI_REVISION == 1:
            pin_to_gpio = self._pin_to_gpio_rev1
        elif GPIO.RPI_REVISION == 2:
            pin_to_gpio = self._pin_to_gpio_rev2
        else:
            pin_to_gpio = self._pin_to_gpio_rev3

        return pin_to_gpio[pin]

    def _gpio_bcm_to_board(self, pin):
        if GPIO.RPI_REVISION == 1:
            pin_to_gpio = self._pin_to_gpio_rev1
        elif GPIO.RPI_REVISION == 2:
            pin_to_gpio = self._pin_to_gpio_rev2
        else:
            pin_to_gpio = self._pin_to_gpio_rev3

        return pin_to_gpio.index(pin)

    def _gpio_get_pin(self, pin):
        if (GPIO.getmode() == GPIO.BOARD and self.GPIOMode == 'BOARD') or (GPIO.getmode() == GPIO.BCM and self.GPIOMode == 'BCM'):
            return pin
        elif GPIO.getmode() == GPIO.BOARD and self.GPIOMode == 'BCM':
            return self._gpio_bcm_to_board(pin)
        elif GPIO.getmode() == GPIO.BCM and self.GPIOMode == 'BOARD':
            return self._gpio_board_to_bcm(pin)
        else:
            return 0

    def _configure_gpio(self):
        self._logger.info("Running RPi.GPIO version %s" % GPIO.VERSION)
        if GPIO.VERSION < "0.6":
            self._logger.error("RPi.GPIO version 0.6.0 or greater required.")
        
        GPIO.setwarnings(False)

        for pin in self._configuredGPIOPins:
            self._logger.debug("Cleaning up pin %s" % pin)
            try:
                GPIO.cleanup(self._gpio_get_pin(pin))
            except (RuntimeError, ValueError) as e:
                self._logger.error(e)
        self._configuredGPIOPins = []

        if GPIO.getmode() is None:
            if self.GPIOMode == 'BOARD':
                GPIO.setmode(GPIO.BOARD)
            elif self.GPIOMode == 'BCM':
                GPIO.setmode(GPIO.BCM)
            else:
                return
        
        self._logger.info("Using GPIO for On/Off")
        self._logger.info("Configuring GPIO for pin %s" % self.onoffGPIOPin)
        try:
            if not self.invertonoffGPIOPin:
                initial_pin_output=GPIO.LOW
            else:
                initial_pin_output=GPIO.HIGH
            GPIO.setup(self._gpio_get_pin(self.onoffGPIOPin), GPIO.OUT, initial=initial_pin_output)
            self._configuredGPIOPins.append(self.onoffGPIOPin)
        except (RuntimeError, ValueError) as e:
            self._logger.error(e)

    def check_light_state(self):
        old_isLightOn = self.isLightOn

        self._logger.debug("Polling Light state...")
        r = 0
        try:
            r = GPIO.input(self._gpio_get_pin(self.onoffGPIOPin))
        except (RuntimeError, ValueError) as e:
            self._logger.error(e)
        self._logger.debug("Result: %s" % r)

        if r==1:
            new_isLightOn = True
        elif r==0:
            new_isLightOn = False

        if self.invertonoffGPIOPin:
            new_isLightOn = not new_isLightOn

        self.isLightOn = new_isLightOn

        self._logger.debug("isLightOn: %s" % self.isLightOn)

        self._plugin_manager.send_plugin_message(self._identifier, dict(isLightOn=self.isLightOn))

    def turn_light_on(self):
        self._logger.info("Switching Light On")

        self._logger.debug("Switching Light On Using GPIO: %s" % self.onoffGPIOPin)
        if not self.invertonoffGPIOPin:
            pin_output=GPIO.HIGH
        else:
            pin_output=GPIO.LOW

        try:
            GPIO.output(self._gpio_get_pin(self.onoffGPIOPin), pin_output)
        except (RuntimeError, ValueError) as e:
            self._logger.error(e)

        self.check_light_state()

    def turn_light_off(self):
        self._logger.info("Switching Light Off")

        self._logger.debug("Switching Light Off Using GPIO: %s" % self.onoffGPIOPin)
        if not self.invertonoffGPIOPin:
            pin_output=GPIO.LOW
        else:
            pin_output=GPIO.HIGH

        try:
            GPIO.output(self._gpio_get_pin(self.onoffGPIOPin), pin_output)
        except (RuntimeError, ValueError) as e:
            self._logger.error(e)

        self.check_light_state()

    def get_api_commands(self):
        return dict(
            turnLightOn=[],
            turnLightOff=[],
            toggleLight=[],
            getLightState=[]
        )

    def on_api_command(self, command, data):
        if not user_permission.can():
            return make_response("Insufficient rights", 403)
        
        if command == 'turnLightOn':
            self.turn_light_on()
        elif command == 'turnLightOff':
            self.turn_light_off()
        elif command == 'toggleLight':
            if self.isLightOn:
                self.turn_light_off()
            else:
                self.turn_light_on()
        elif command == 'getLightState':
            return jsonify(isLightOn=self.isLightOn)

    def get_settings_defaults(self):
        return dict(
            GPIOMode = 'BOARD',
            onoffGPIOPin = 0,
            invertonoffGPIOPin = False
        )

    def on_settings_save(self, data):
        old_GPIOMode = self.GPIOMode
        old_onoffGPIOPin = self.onoffGPIOPin
        
        octoprint.plugin.SettingsPlugin.on_settings_save(self, data)
        
        self.GPIOMode = self._settings.get(["GPIOMode"])
        self.onoffGPIOPin = self._settings.get_int(["onoffGPIOPin"])
        self.invertonoffGPIOPin = self._settings.get_boolean(["invertonoffGPIOPin"])
        
        if (old_GPIOMode != self.GPIOMode or
           old_onoffGPIOPin != self.onoffGPIOPin):
            self._configure_gpio()

    def get_template_configs(self):
        return [
            dict(type="settings", custom_bindings=False)
        ]

    def get_assets(self):
        return {
            "js": ["js/lightcontrol.js"]
        } 

    def get_update_information(self):
        return dict(
            lightcontrol=dict(
                displayName="Light Control",
                displayVersion=self._plugin_version,

                # version check: github repository
                type="github_release",
                user="kantlivelong",
                repo="OctoPrint-LightControl",
                current=self._plugin_version,

                # update method: pip w/ dependency links
                pip="https://github.com/kantlivelong/OctoPrint-LightControl/archive/{target_version}.zip"
            )
        )

__plugin_name__ = "Light Control"

def __plugin_load__():
    global __plugin_implementation__
    __plugin_implementation__ = LightControl()

    global __plugin_hooks__
    __plugin_hooks__ = {
        "octoprint.plugin.softwareupdate.check_config": __plugin_implementation__.get_update_information
    }
