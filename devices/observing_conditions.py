"""
This module contains the weather class. When get_status() is called, the weather situation
is evaluated and self.wx_is_ok and self.open_is_ok are evaluated and published along
with self.status, a dictionary.

This module should be expanded to integrate multiple Wx sources, particularly Davis and
SkyAlert.

Weather holds are counted only when they INITIATE within the Observing window. So if a
hold started just before the window and opening was late that does not count for anti-
flapping purposes.

This module sends 'signals' through the Events layer then TO the enclosure by checking
as sender that an OPEN for example can get through the Events layer. It is Mandatory
the receiver (the enclosure in this case) also checks the Events layer. The events layer
is populated once per observing day with default values. However the dictionary entries
can be modified for debugging or simulation purposes.
"""

import json
import socket
import time
import os
import win32com.client
# import redis
import traceback

from global_yard import g_dev
# from site_config import get_ocn_status
from wema_utility import plog


def linearize_unihedron(uni_value):  # Need to be coefficients in config.
    #  Based on 20180811 data
    uni_value = float(uni_value)
    if uni_value < -1.9:
        uni_corr = 2.5 ** (-5.85 - uni_value)
    elif uni_value < -3.8:
        uni_corr = 2.5 ** (-5.15 - uni_value)
    elif uni_value <= -12:
        uni_corr = 2.5 ** (-4.88 - uni_value)
    else:
        uni_corr = 6000
    return uni_corr


#  Unused
def f_to_c(f):
    return round(5 * (f - 32) / 9, 2)


class ObservingConditions:
    def __init__(self, driver: str, name: str, config: dict, astro_events):
        self.name = name
        self.astro_events = astro_events
        self.siteid = config["wema_name"]
        self.config = config
        g_dev["ocn"] = self
        # g_dev['obs'].night_fitzgerald_number = 0,  # 20230709 initialse this varable to permissive state WER
        self.sample_time = 0
        self.ok_to_open = "No"  # This is a default on startup.
        self.observing_condtions_message = "-"
        self.wx_is_ok = False
        self.clamp_latch = False
        self.wait_time = 0  # A countdown to re-open
        self.wait_time = 0  # A countdown to re-open
        self.wx_system_enable = True  # Purely a debugging aid.
        self.wx_test_cycle = 0
        self.prior_status = None
        self.prior_status_2 = None
        self.wmd_fail_counter = 0
        self.temperature = self.config["reference_ambient"]  # Index needs
        self.pressure = self.config["reference_pressure"]  # to be months.
        self.unihedron_connected = True  # NB NB NB His needs improving, drive from config
        self.hostname = socket.gethostname()

        # =============================================================================
        #         Note site_in_automatic found in the Enclosure object.
        # =============================================================================

        if self.hostname in self.config["wema_hostname"]:

            self.is_wema = True
            self.is_process = False
        else:
            self.is_wema = False
            self.is_process = True

        # self.site_is_custom = False

        # if self.config["site_is_custom"]:
        #     self.site_is_custom = True   #  Note OCN has no associated commands.
        #     #Here we monkey patch
        #     from site_config import get_ocn_status
        #     self.get_status = get_ocn_status
        #     #Get current ocn status just as a test.
        #     try:
        #         self.status = self.get_status(g_dev)
        #     except:
        #         plog("Test: self.get_status(g_dev) did not respond.")

        #  This is meant to be thea generic Observing_condition code
        #  instance that can be accessed by a simple site or by the WEMA,
        #  assuming the transducers are connected to the WEMA.
        # self.obsid_is_generic = True

        if not (driver == None):
            win32com.client.pythoncom.CoInitialize()
            self.sky_monitor = win32com.client.Dispatch(driver)
            self.sky_monitor.connected = True
            try:
                driver_2 = config["observing_conditions"]["observing_conditions1"][
                    "driver_2"
                ]
                self.sky_monitor_oktoopen = win32com.client.Dispatch(driver_2)
                self.sky_monitor_oktoopen.Connected = True
                driver_3 = config["observing_conditions"]["observing_conditions1"][
                    "driver_3"
                ]
            except:
                plog('ocn Drivers 2 or 3 not present.')
                driver_2 = None
                driver_3 = None
            if driver_3 is not None:
                self.sky_monitor_oktoimage = win32com.client.Dispatch(driver_3)
                self.sky_monitor_oktoimage.Connected = True
                plog("observing_conditions: sky_monitors connected = True")

            if config["observing_conditions"]["observing_conditions1"]["has_unihedron"]:

                unihedron_path = self.config['wema_path'] + self.config['wema_name'] + "/unihedron"
                if not os.path.exists(unihedron_path):
                    os.makedirs(unihedron_path)

                self.unihedron_connected = True
                try:
                    driver = config["observing_conditions"]["observing_conditions1"][
                        "uni_driver"
                    ]
                    port = config["observing_conditions"]["observing_conditions1"][
                        "unihedron_port"
                    ]
                    self.unihedron = win32com.client.Dispatch(driver)
                    self.unihedron.Connected = True
                    plog(
                        "observing_conditions: Unihedron is connected, on COM"
                        + str(port)
                    )
                except:
                    plog(
                        "Unihedron on Port COM" + str(port) + " is disconnected. Observing will proceed."
                    )
                    self.unihedron_connected = False
                    # NB NB if no unihedron is installed the status code needs to not report it.
            else:
                self.unihedron_connected = False

        self.rain_limit_setting = self.config['rain_limit']
        self.humidity_limit_setting = self.config['humidity_limit']
        self.windspeed_limit_setting = self.config['windspeed_limit']
        self.lightning_limit_setting = self.config['lightning_limit']
        self.temp_minus_dew_setting = self.config['temperature_minus_dewpoint_limit']
        self.sky_temp_limit_setting = self.config['sky_temperature_limit']
        self.cloud_cover_limit_setting = self.config['cloud_cover_limit']
        self.lowest_temperature_setting = self.config['lowest_ambient_temperature']
        self.highest_temperature_setting = self.config['highest_ambient_temperature']

        self.warning_rain_limit_setting = self.config['warning_rain_limit']
        self.warning_humidity_limit_setting = self.config['warning_humidity_limit']
        self.warning_windspeed_limit_setting = self.config['warning_windspeed_limit']
        self.warning_lightning_limit_setting = self.config['warning_lightning_limit']
        self.warning_temp_minus_dew_setting = self.config['warning_temperature_minus_dewpoint_limit']
        self.warning_sky_temp_limit_setting = self.config['warning_sky_temperature_limit']
        self.warning_cloud_cover_limit_setting = self.config['warning_cloud_cover_limit']
        self.warning_lowest_temperature_setting = self.config['warning_lowest_ambient_temperature']
        self.warning_highest_temperature_setting = self.config['warning_highest_ambient_temperature']

        self.rain_limit_on = self.config['rain_limit_on']
        self.humidity_limit_on = self.config['humidity_limit_on']
        self.windspeed_limit_on = self.config['windspeed_limit_on']
        self.lightning_limit_on = self.config['lightning_limit_on']
        self.temp_minus_dew_on = self.config['temperature_minus_dewpoint_limit_on']
        self.sky_temperature_limit_on = self.config['sky_temperature_limit_on']
        self.cloud_cover_limit_on = self.config['cloud_cover_limit_on']
        self.lowest_temperature_on = self.config['lowest_ambient_temperature_on']
        self.highest_temperature_on = self.config['highest_ambient_temperature_on']

        # self.wx_hold = False
        self.last_wx = None

    def get_status(self):
        """
        Regularly calling this routine returns weather status dict for AWS,
        evaluates the Wx reporting and manages temporary closes,
        known as weather-holds

        Returns
        -------
        status : TYPE
            DESCRIPTION.

        """
        # Just need to initialise this.
        status = None
        # This is purely generic code for a generic site.
        # It may be overwritten with a monkey patch found in the appropriate config.py.
        if not self.is_wema: #and self.site_is_custom:  # EG., this was written first for SRO.                                        #  system is a proxoy for having a WEMA
            # This is NOT the normal ARO path
            if self.config["site_IPC_mechanism"] == "shares":
                try:
                    weather = open(g_dev["wema_share_path"] + "weather.txt", "r")
                    status = json.loads(weather.readline())
                    weather.close()
                    self.status = status
                    self.prior_status = status
                    g_dev["ocn"].status = status
                    return status
                except:
                    try:
                        time.sleep(3)
                        weather = open(g_dev["wema_share_path"] + "weather.txt", "r")
                        status = json.loads(weather.readline())
                        weather.close()
                        self.status = status
                        self.prior_status = status
                        g_dev["ocn"].status = status
                        return status
                    except:
                        try:
                            time.sleep(3)
                            weather = open(
                                g_dev["wema_share_path"] + "weather.txt", "r"
                            )
                            status = json.loads(weather.readline())
                            weather.close()
                            self.status = status
                            self.prior_status = status
                            g_dev["ocn"].status = status
                            return status
                        except:
                            plog("Using prior OCN status after 4 failures.")
                            g_dev["ocn"].status = self.prior_status
                            return self.prior_status


        elif self.config['observing_conditions']['observing_conditions1']["name"] == 'Boltwood Custom for ARO':
            #This is the normal path for ARO

            try:
                with open("C:\ptr\wema_transfer\\boltwood.txt", 'r') as bw_rec:
                    bw1 = bw_rec.readline().split()
                with open('W:\skyalert\weatherdata_nw.txt', 'r') as bw_rec:
                    sa_nw = bw_rec.readline().split()
                print(bw1)
                print(sa_nw)
                rate = [0, 0, 1, 2]
                # cover = ['Clear', 'Cloudy', 'Very Cloudy']
                cover = [0.0, 50.0, 100.0]
                self.temperature = round((float(bw1[5]) + float(sa_nw[5])) / 2., 1)
                self.sky_temp = round((float(bw1[4]) + float(sa_nw[4])) / 2., 2)
                self.sky_minus_ambient = round(self.sky_temp - self.temperature, 2)
                self.humidity = round((float(bw1[8]) + float(sa_nw[8])) / 2., 1)
                self.dewpoint = round((float(bw1[9]) + float(sa_nw[9])) / 2., 2)
                self.windspeed = round(1.60934 * (float(bw1[7]) + float(sa_nw[7])) / 2., 2)  # incoming mph output km/hs
                self.time_since = int((float(bw1[13]) + float(sa_nw[13])) / 2.)
                self.time_of_update = round((float(bw1[14]) + float(sa_nw[14])) / 2., 5)
                self.rain_wet_current = max(int(bw1[11]), int(sa_nw[12]), int(bw1[11]), int(sa_nw[12]))
                self.cloud_condition = max(int(bw1[15]), int(sa_nw[15]))
                self.rain_wet_condition = max(int(bw1[16]), int(sa_nw[16]), int(bw1[17]), int(sa_nw[17]))
                self.daylight_condition = max(int(bw1[18]), int(sa_nw[18]))
                self.req_close = bool(bw1[19])
                self.rain_rate = rate[self.rain_wet_condition]
                self.cloud_cover = cover[self.cloud_condition]
                # At this point cloud is grossly different from reality based on the Clarity app reporting.

                # breakpoint()
                status = {}
                illum, mag = self.astro_events.illuminationNow()
                # illum = float(redis_monitor["illum lux"])
                if illum > 500:
                    illum = int(illum)
                else:
                    illum = round(illum, 3)
                if self.unihedron_connected:
                    try:
                        uni_measure = (
                            self.unihedron.SkyQuality
                        )  # Provenance of 20.01 is dubious 20200504 WER
                    except:
                        uni_measure = 0
                else:
                    uni_measure = 0
                if uni_measure == 0:
                    uni_measure = round(
                        (mag - 20.01), 2
                    )  # Fixes Unihedron when sky is too bright
                    status["meas_sky_mpsas"] = uni_measure
                    self.meas_sky_lux = illum
                else:
                    self.meas_sky_lux = linearize_unihedron(uni_measure)
                    status["meas_sky_mpsas"] = uni_measure

                # self.temperature = round((bw1[5] + sa_nw[5])/2., 2)
                self.humidity
                try:  # NB NB Boltwood vs. SkyAlert difference.  What about SRO?
                    self.pressure = self.sky_monitor.Pressure
                    assert self.pressure > 200

                except:
                    self.pressure = self.config["reference_pressure"]

                # NB NB NB This is a very odd problem which showed up at MRC.

                try:
                    self.new_pressure = round(float(self.pressure[0]), 2)  # was [0]), 2)
                except:
                    self.new_pressure = round(float(self.pressure), 2)

                status = {
                    "temperature_C": self.temperature,
                    "pressure_mbar": self.new_pressure,
                    "humidity_%": self.humidity,
                    "dewpoint_C": self.dewpoint,
                    "sky_temp_C": self.sky_minus_ambient,
                    "last_sky_update_s": self.time_since,
                    "wind_m/s": self.windspeed,
                    "rain_rate": self.rain_rate,
                    "solar_flux_w/m^2": None,
                    "cloud_cover_%": self.cloud_cover,
                    "calc_HSI_lux": illum,
                    "calc_sky_mpsas": round(uni_measure, 2),  # Provenance of 20.01 is dubious 20200504 WER
                    "open_ok": self.ok_to_open,
                    "lightning_strike_radius km": 'n/a',
                    "general_obscuration %": 'n/a',
                    "photometric extinction k'": 'n/a',
                    # "wx_hold": None,
                    # "hold_duration": 0,
                }

                # MTF adding in necessary "ok to open" stuff to the BOLTWOOD

                rain_limit_setting = self.config['rain_limit']
                humidity_limit_setting = self.config['humidity_limit']
                windspeed_limit_setting = self.config['windspeed_limit']
                temp_minus_dew_setting = self.config['temperature_minus_dewpoint_limit']
                sky_temp_limit_setting = self.config['sky_temperature_limit']
                cloud_cover_limit_setting = self.config['cloud_cover_limit']
                lowest_temperature_setting = self.config['lowest_ambient_temperature']
                highest_temperature_setting = self.config['highest_ambient_temperature']

                wx_reasons = []

                rain_limit = self.sky_monitor.RainRate > rain_limit_setting
                if rain_limit:
                    plog("Reported rain rate in mm/hr:  ", self.sky_monitor.RainRate)
                    wx_reasons.append('Rain > ' + str(rain_limit_setting))
                humidity_limit = self.sky_monitor.Humidity < humidity_limit_setting
                if not humidity_limit:
                    wx_reasons.append('Humidity >= ' + str(humidity_limit_setting) + '%')
                wind_limit = (
                        self.sky_monitor.WindSpeed < windspeed_limit_setting
                )  # sky_monitor reports km/h, Clarity may report in MPH
                if not wind_limit:
                    wx_reasons.append('Wind > ' + str(windspeed_limit_setting) + ' km/h')
                dewpoint_gap = (
                    not (self.sky_monitor.Temperature - self.sky_monitor.DewPoint) < temp_minus_dew_setting
                )
                if not dewpoint_gap:
                    wx_reasons.append('Ambient - Dewpoint < ' + str(temp_minus_dew_setting) + 'C')
                sky_amb_limit = (
                                        self.sky_monitor.SkyTemperature - self.sky_monitor.Temperature
                                ) < sky_temp_limit_setting  # NB THIS NEEDS ATTENTION, Sky alert defaults to -17
                if not sky_amb_limit:
                    wx_reasons.append('(sky - amb) > ' + str(sky_temp_limit_setting) + 'C')
                try:
                    cloud_cover_value = float(self.sky_monitor.CloudCover)
                    status['cloud_cover_%'] = round(cloud_cover_value, 0)
                    if cloud_cover_value <= cloud_cover_limit_setting:
                        cloud_cover = False
                    else:
                        cloud_cover = True
                        wx_reasons.append('>=' + str(cloud_cover_limit_setting) + '% Cloudy')
                except:
                    status['cloud_cover_%'] = "no report"
                    cloud_cover = True  # We cannot use this signal to force a wX hold or close
                self.current_ambient = round(self.temperature, 2)
                temp_bounds = lowest_temperature_setting < self.sky_monitor.Temperature < highest_temperature_setting

                if not temp_bounds:
                    wx_reasons.append('amb temp out of range')

                self.wx_is_ok = (
                        dewpoint_gap
                        and temp_bounds
                        and wind_limit
                        and sky_amb_limit
                        and humidity_limit
                    # and not rain_limit
                    # and not cloud_cover
                )
                #  NB wx_is_ok does not include ambient light or altitude of the Sun
                # the notion of Obs OK should bring in Sun Elevation and or ambient light.

                if self.sky_monitor.RainRate > 0.0:
                    plog("%$%^%#^$%#*!$^#%$*@#^$%*@#^$%*#%$^&@#$*@&")
                    plog("Rain Rate is 1.0")
                    # plog('Rain > ' + str(rain_limit_setting))
                    plog("This is usually a glitch so ignoring. Higher rain rates will trigger roof.")
                    plog("%$%^%#^$%#*!$^#%$*@#^$%*@#^$%*#%$^&@#$*@&")

                if self.wx_is_ok:
                    wx_str = "Yes"
                    status["wx_ok"] = "Yes"
                    # plog('Wx Ok?  ', status["wx_ok"])
                else:
                    wx_str = "No"  # Ideally we add the dominant reason in priority order.
                    status["wx_ok"] = "No"
                    plog('Wx Ok: ', status["wx_ok"], wx_reasons)

                g_dev["wx_ok"] = self.wx_is_ok

                return status
            except:
                plog(traceback.format_exc())

                plog('something went wrong with the boltwood stuff')
                plog('above is an unglamourous traceback but continuing onwards')
                return None

        elif self.is_wema:  # These operations are common to a generic single computer or wema site.
            ## Here we get the status from local devices
            status = {}
            illum, mag = self.astro_events.illuminationNow()
            # illum = float(redis_monitor["illum lux"])
            if illum > 500:
                illum = int(illum)
            else:
                illum = round(illum, 3)
            if self.unihedron_connected:
                try:
                    uni_measure = (
                        self.unihedron.SkyQuality
                    )  # Provenance of 20.01 is dubious 20200504 WER
                except:
                    uni_measure = 0
            else:
                uni_measure = 0
            if uni_measure == 0:
                uni_measure = round(
                    (mag - 20.01), 2
                )  # Fixes Unihedron when sky is too bright
                status["meas_sky_mpsas"] = uni_measure
                self.meas_sky_lux = illum
            else:
                self.meas_sky_lux = linearize_unihedron(uni_measure)
                status["meas_sky_mpsas"] = uni_measure

            self.temperature = round(self.sky_monitor.Temperature, 2)
            try:  # NB NB Boltwood vs. SkyAlert difference.  What about SRO?
                self.pressure = self.sky_monitor.Pressure
                assert self.pressure > 200

            except:
                self.pressure = self.config["reference_pressure"]

            # NB NB NB This is a very odd problem which showed up at MRC.

            try:
                self.new_pressure = round(float(self.pressure[0]), 2)  # was [0]), 2)  #NB this is an unfinished lame attempt to index by month.
            except:
                self.new_pressure = round(float(self.pressure), 2)
            try:
                status = {
                    "temperature_C": round(self.temperature, 2),
                    "pressure_mbar": self.new_pressure,
                    "humidity_%": self.sky_monitor.Humidity,
                    "dewpoint_C": self.sky_monitor.DewPoint,
                    "sky_temp_C": round(self.sky_monitor.SkyTemperature, 2),
                    "last_sky_update_s": round(
                        self.sky_monitor.TimeSinceLastUpdate("SkyTemperature"), 2
                    ),
                    "wind_m/s": abs(round(self.sky_monitor.WindSpeed, 2)),
                    "rain_rate": self.sky_monitor.RainRate,
                    "solar_flux_w/m^2": None,
                    "cloud_cover_%": str(self.sky_monitor.CloudCover),
                    "calc_HSI_lux": illum,
                    "calc_sky_mpsas": round(
                        uni_measure, 2
                    ),  # Provenance of 20.01 is dubious 20200504 WER
                    "open_ok": self.ok_to_open,
                    "lightning_strike_radius km": 'n/a',
                    "general_obscuration %": 'n/a',
                    "photometric extinction k'": 'n/a',
                    # "wx_hold": None,
                    # "hold_duration": 0,
                }
            except:
                status = {
                    "temperature_C": round(self.temperature, 2),
                    "pressure_mbar": self.new_pressure,
                    "humidity_%": self.sky_monitor.Humidity,
                    "dewpoint_C": self.sky_monitor.DewPoint,
                    "sky_temp_C": round(self.sky_monitor.SkyTemperature, 2),
                    "last_sky_update_s": round(
                        self.sky_monitor.TimeSinceLastUpdate("SkyTemperature"), 2
                    ),
                    "wind_m/s": abs(round(self.sky_monitor.WindSpeed, 2)),
                    "rain_rate": self.sky_monitor.RainRate,
                    "solar_flux_w/m^2": None,
                    "cloud_cover_%": "unknown",  # str(self.sky_monitor.CloudCover), # Sometimes faults.
                    "calc_HSI_lux": illum,
                    "calc_sky_mpsas": round(
                        uni_measure, 2
                    ),  # Provenance of 20.01 is dubious 20200504 WER
                    "open_ok": self.ok_to_open,
                    "lightning_strike_radius km": 'n/a',
                    "general_obscuration %": 'n/a',
                    "photometric extinction k'": 'n/a',
                    # "wx_hold": None,
                    # "hold_duration": 0,
                }

            wx_reasons = []

            rain_limit = self.sky_monitor.RainRate > self.rain_limit_setting
            if rain_limit:
                plog("Reported rain rate in mm/hr:  ", self.sky_monitor.RainRate)
                wx_reasons.append('Rain > ' + str(self.rain_limit_setting))
            humidity_limit = self.sky_monitor.Humidity < self.humidity_limit_setting
            if not humidity_limit:
                wx_reasons.append('Humidity >= ' + str(self.humidity_limit_setting) + '%')
            wind_limit = (
                    self.sky_monitor.WindSpeed < self.windspeed_limit_setting
            )  # sky_monitor reports km/h, Clarity may report in MPH
            if not wind_limit:
                wx_reasons.append('Wind > ' + str(self.windspeed_limit_setting) + ' km/h')
            dewpoint_gap = (
                not (self.sky_monitor.Temperature - self.sky_monitor.DewPoint) < self.temp_minus_dew_setting
            )
            if not dewpoint_gap:
                wx_reasons.append('Ambient - Dewpoint < ' + str(self.temp_minus_dew_setting) + 'C')
            sky_amb_limit = (
                                    self.sky_monitor.SkyTemperature - self.sky_monitor.Temperature
                            ) < self.sky_temp_limit_setting  # NB THIS NEEDS ATTENTION, Sky alert defaults to -17
            if not sky_amb_limit:
                wx_reasons.append('(sky - amb) > ' + str(self.sky_temp_limit_setting) + 'C')
            try:
                cloud_cover_value = float(self.sky_monitor.CloudCover)
                status['cloud_cover_%'] = round(cloud_cover_value, 0)
                if cloud_cover_value <= self.cloud_cover_limit_setting:
                    cloud_cover = False
                else:
                    cloud_cover = True
                    wx_reasons.append('>=' + str(self.cloud_cover_limit_setting) + '% Cloudy')
            except:
                status['cloud_cover_%'] = "no report"
                cloud_cover = True  # We cannot use this signal to force a wX hold or close
            self.current_ambient = round(self.temperature, 2)
            temp_bounds = self.lowest_temperature_setting < self.sky_monitor.Temperature < self.highest_temperature_setting

            if not temp_bounds:
                wx_reasons.append('amb temp out of range')

            self.wx_is_ok = (
                    (dewpoint_gap and self.temp_minus_dew_on)
                    and (temp_bounds and (self.lowest_temperature_on or self.highest_temperature_on))
                    and (wind_limit and self.windspeed_limit_on)
                    and (sky_amb_limit and self.sky_temperature_limit_on)
                    and (humidity_limit and self.humidity_limit_on)
                    and not (rain_limit and self.rain_limit_on)
                    and not (cloud_cover and self.cloud_cover_limit_on)
            )
            #  NB wx_is_ok does not include ambient light or altitude of the Sun
            # the notion of Obs OK should bring in Sun Elevation and or ambient light.

            if self.sky_monitor.RainRate > 0.0:
                plog("%$%^%#^$%#*!$^#%$*@#^$%*@#^$%*#%$^&@#$*@&")
                plog("Rain Rate is 1.0")
                # plog('Rain > ' + str(rain_limit_setting))
                plog("This is usually a glitch so ignoring. Higher rain rates will trigger roof.")
                plog("%$%^%#^$%#*!$^#%$*@#^$%*@#^$%*#%$^&@#$*@&")

            if self.wx_is_ok:
                wx_str = "Yes"
                status["wx_ok"] = "Yes"
                # plog('Wx Ok?  ', status["wx_ok"])
            else:
                wx_str = "No"  # Ideally we add the dominant reason in priority order.
                status["wx_ok"] = "No"
                plog('Wx Ok: ', status["wx_ok"], wx_reasons)

            g_dev["wx_ok"] = self.wx_is_ok
            # g_dev['ocn'].wx_hold = False

            # if self.config["site_IPC_mechanism"] == "shares":
            #     weather_txt = self.config["wema_write_share_path"] + "weather.txt"
            #     try:
            #         with open(weather_txt, "w", encoding="utf-8") as f:
            #             f.write(json.dumps(status))
            #     except IOError:
            #         tries = 1
            #         while tries < 5:
            #             # Wait 3 seconds and try writing to file again, up to 3 more times.
            #             plog(
            #                 f"Attempt {tries} to write weather status failed. Trying again."
            #             )
            #             time.sleep(3)
            #             with open(weather_txt, "w", encoding="utf-8") as f:
            #                 f.write(json.dumps(status))
            #                 if not weather_txt.closed:
            #                     break
            #             tries += 1

            # Only write when around dark, put in CSV format, used to calibrate Unihedron.
            # breakpoint()
            sunZ88Op, sunZ88Cl, sunrise, ephemNow = g_dev[
                "wema"
            ].astro_events.getSunEvents()
            two_hours = (
                    2 / 24
            )  # Note changed to 2 hours. NB NB NB The times need changing to bracket skyflats.
            if (sunZ88Op - two_hours < ephemNow < sunZ88Cl + two_hours) and (
                    time.time() >= self.sample_time + 60
            ):  # Once a minute.

                try:
                    wl = open(self.config['wema_path'] + self.config['wema_name'] + "/unihedron/wx_log.txt", "a")
                    wl.write(
                        str(time.time())
                        + ", "
                        + str(illum)
                        + ", "
                        + str(mag - 20.01)
                        + ", "
                        + str(uni_measure)
                        + ", \n"
                    )
                    wl.close()
                    self.sample_time = time.time()
                except:
                    self.sample_time = time.time() - 61

            # Now let's compute Wx hold condition. Class is set up to assume Wx has been good.
            # The very first time though at Noon, self.open_is_ok will always be False but the
            # Weather, which does not include ambient light, can be good. We will assume that
            # changes in ambient light are dealt with more by the Events module.

            # We want the wx_hold signal to go up and down as a guage on the quality of the
            # afternoon. If there are a lot of cycles, that indicates unsettled conditons even
            # if any particular instant is perfect. So we set self.wx_hold to false during class
            # __init__().
            # When we get to this point of the code first time we expect self.wx_is_ok to be true

            # obs_win_begin, sunset, sunrise, ephemNow = self.astro_events.getSunEvents()
            # wx_delay_time = 900
            # try:
            #    multiplier = min(len(wx_reasons),3)
            # except:
            #    multiplier = 1
            # wx_delay_time *= multiplier/2   #Stretch out the Wx hold if there are multiple reasons

            # if (
            #    self.wx_is_ok and self.wx_system_enable
            # ) and not self.wx_hold:  # Normal condition, possibly nothing to do.
            #    self.wx_hold_last_updated = time.time()
            # elif not self.wx_is_ok and not self.wx_hold:  # Wx bad and no hold yet.
            # Bingo we need to start a cycle
            # self.wx_hold = True
            # self.wx_hold_until_time = (
            #     t := time.time() + wx_delay_time
            # )  # 15 minutes   Make configurable
            # self.wx_hold_tally += 1  #  This counts all day and night long.
            # self.wx_hold_last_updated = t
            # if (
            #     obs_win_begin <= ephemNow <= sunrise
            # ):  # Gate the real holds to be in the Observing window.
            #     self.wx_hold_count += 1
            #     # We choose to let the enclosure manager handle the close.
            #     plog(
            #         "Wx hold asserted, flap#:",
            #         self.wx_hold_count,
            #         self.wx_hold_tally,
            #     )
            # else:
            #     plog(
            #         "Wx Hold -- out of Observing window.",
            #         self.wx_hold_count,
            #         self.wx_hold_tally,
            #     )
            # elif not self.wx_is_ok and self.wx_hold:  # WX is bad and we are on hold.
            #     self.wx_hold_last_updated = time.time()
            #     # Stay here as long as we need to.
            #     self.wx_hold_until_time = (t := time.time() + wx_delay_time)
            #     if self.wx_system_enable:
            #         pass
            # elif self.wx_is_ok and self.wx_hold:  # Wx now good and still on hold.
            #     if self.wx_hold_count < 3:
            #         if time.time() >= self.wx_hold_until_time and not self.wx_clamp:
            #             # Time to release the hold.
            #             self.wx_hold = False
            #             self.wx_hold_until_time = (
            #                 time.time() + wx_delay_time
            #             )  # Keep pushing the recovery out
            #             self.wx_hold_last_updated = time.time()
            #             plog(
            #                 "Wx hold released, flap#, tally#:",
            #                 self.wx_hold_count,
            #                 self.wx_hold_tally,
            #             )
            #             # We choose to let the enclosure manager diecide it needs to re-open.
            #     else:
            #         # Never release the THIRD hold without some special high level intervention.
            #         if not self.clamp_latch:
            #             plog("Sorry, Tobor is clamping enclosure shut for the night.")
            #         self.clamp_latch = True
            #         self.wx_clamp = True

            # self.wx_hold_last_updated = time.time()
            # if self.wx_hold:
            #    self.wx_to_go = round((self.wx_hold_until_time - time.time()), 0)
            #    status["hold_duration"] = self.wx_to_go
            # MTF COMMENTED THIS OUT BECAUSE IT WAS SENDING A STATUS EVERY 20 SECONDS
            # try:
            #    g_dev['obs'].send_to_user(wx_reasons)
            # except:
            #    pass
            # else:
            #    status["hold_duration"] = 0.0
            self.status = status
            g_dev["ocn"].status = status

            return status

    # def get_noocndevice_status(self):

    #     illum, mag = g_dev["evnt"].illuminationNow()

    #     if g_dev['seq'].weather_report_is_acceptable_to_observe:
    #         openok='Yes'
    #     else:
    #         openok='No'

    #     status = {
    #         #"temperature_C": 0.0,
    #         #"pressure_mbar": 0.0,
    #         #"humidity_%": 0.0,
    #         #"dewpoint_C": 0.0,
    #         #"sky_temp_C": 0.0,
    #         #"last_sky_update_s": 0.0,
    #         #"wind_m/s": 0.0,
    #         #"rain_rate": 0.0,
    #         #"solar_flux_w/m^2": None,
    #         #"cloud_cover_%": 0.0,
    #         #"calc_HSI_lux": illum,
    #         #"calc_sky_mpsas": 0.0,  # Provenance of 20.01 is dubious 20200504 WER
    #         "open_ok": openok, #self.ok_to_open,
    #         "wx_hold": 'no',
    #         "hold_duration": float(0.0),
    #     }

    #     #quick=[]
    #     #if self.obsid_is_specific:
    #     #    self.status = self.get_status(g_dev)  # Get current state.
    #     #else:
    #     #    self.status = self.get_status()

    #     # NB NB NB it is safer to make this a dict rather than a positionally dependant list.
    #     #quick.append(time.time())
    #     #quick.append(float(0))
    #     #quick.append(float(0))
    #     #quick.append(float(0))
    #     #quick.append(float(0))
    #     #quick.append(float(0))
    #     #quick.append(float(0))  # 20200329 a SWAG!
    #     #quick.append(float(illum))  # Add Solar, Lunar elev and phase
    #     #quick.append(float(self.meas_sky_lux))  # intended for Unihedron
    #     return status

    def get_quick_status(self, quick):

        if self.obsid_is_specific:
            self.status = self.get_status(g_dev)  # Get current state.
        else:
            self.status = self.get_status()
        illum, mag = g_dev["evnt"].illuminationNow()
        # NB NB NB it is safer to make this a dict rather than a positionally dependant list.
        quick.append(time.time())
        quick.append(float(self.status["sky_temp_C"]))
        quick.append(float(self.status["temperature_C"]))
        quick.append(float(self.status["humidity_%"]))
        quick.append(float(self.status["dewpoint_C"]))
        quick.append(float(abs(self.status["wind_m/s"])))
        quick.append(float(self.status["pressure_mbar"]))  # 20200329 a SWAG!
        quick.append(float(illum))  # Add Solar, Lunar elev and phase
        if self.unihedron_connected:
            uni_measure = 0  # wx['meas_sky_mpsas']   #NB NB note we are about to average logarithms.
        else:
            uni_measure = 0
        if uni_measure == 0:
            uni_measure = round(
                (mag - 20.01), 2
            )  # Fixes Unihedron when sky is too bright
            quick.append(float(uni_measure))
            self.meas_sky_lux = illum
        else:
            self.meas_sky_lux = linearize_unihedron(uni_measure)
            quick.append(float(self.meas_sky_lux))  # intended for Unihedron
        return quick

    def get_average_status(self, pre, post):
        average = []
        average.append(round((pre[0] + post[0]) / 2, 3))
        average.append(round((pre[1] + post[1]) / 2, 1))
        average.append(round((pre[2] + post[2]) / 2, 1))
        average.append(round((pre[3] + post[3]) / 2, 1))
        average.append(round((pre[4] + post[4]) / 2, 1))
        average.append(round((pre[5] + post[5]) / 2, 1))
        average.append(round((pre[6] + post[6]) / 2, 2))
        average.append(round((pre[7] + post[7]) / 2, 3))
        average.append(round((pre[8] + post[8]) / 2, 1))
        return average

    # def parse_command(self, command):
    #     # The only possible Wx command is test Wx hold.  NB NB NB No longer true.
    #     req = command["required_params"]
    #     opt = command["optional_params"]
    #     action = command["action"]
    #     if action is not None:
    #         pass
    #         # self.move_relative_command(req, opt)   ???
    #     else:
    #         plog(f"Command <{action}> not recognized in Ocn")

    # ###################################
    #   Observing Conditions Commands  #
    # ###################################


if __name__ == "__main__":
    pass
