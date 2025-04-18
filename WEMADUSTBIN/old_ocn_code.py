# -*- coding: utf-8 -*-
"""
Created on Fri Apr 18 20:18:12 2025

@author: obs
"""

# def calculate_cloud_fraction(T_sky_C, T_clear_C=-20, T_cloud_C=3):
#     """
#     Calculate fractional cloud cover based on sky temperature in Celsius.

#     Parameters:
#     T_sky_C (float): Measured sky temperature in Celsius.
#     T_clear_C (float): Clear sky temperature in Celsius (default: -43C).
#     T_cloud_C (float): Overcast sky temperature in Celsius (default: 7C).

#     Returns:
#     float: Fractional cloud cover (0 to 1)
#     """
#     if T_sky_C < T_clear_C:
#         return 0.0  # Fully clear sky
#     elif T_sky_C > T_cloud_C:
#         return 1.0  # Fully overcast sky

#     return (T_sky_C - T_clear_C) / (T_cloud_C - T_clear_C)

# def calculate_cloud_fraction(T_sky_C, T_clear_C=-20, T_cloud_C=3, n=1):
#     """
#     Calculate fractional cloud cover based on a nonlinear function of sky temperature.

#     Parameters:
#     T_sky_C (float): Measured sky temperature in Celsius.
#     T_clear_C (float): Clear sky temperature in Celsius (default: -20C).
#     T_cloud_C (float): Overcast sky temperature in Celsius (default: 3C).
#     n (float): Nonlinearity exponent (default: 2, adjust based on empirical data).
    
#     MTF - SO FAR, n=1 seems more realistic. Higher numbers underestimate cloud cover

#     Returns:
#     float: Fractional cloud cover (0 to 1)
#     """
#     if T_sky_C <= T_clear_C:
#         return 0.0  # Fully clear sky
#     elif T_sky_C >= T_cloud_C:
#         return 1.0  # Fully overcast sky

#     # Compute nonlinear cloud fraction
#     return ((T_sky_C - T_clear_C) / (T_cloud_C - T_clear_C)) ** n




def calculate_cloud_fraction(T_sky_C, T_ambient_C, RH, 
                             T_cloud_C=3, n=1, avg_RH=50):
    """
    Improved cloud fraction estimation incorporating ambient temperature and humidity.
    Uses an average humidity value when RH is set to -1.

    Parameters:
    T_sky_C (float): Measured sky temperature in Celsius.
    T_ambient_C (float): Ambient air temperature in Celsius.
    RH (float): Relative Humidity in percentage (0-100). Use -1 to apply average RH.
    T_cloud_C (float): Overcast sky temperature in Celsius (default: 3C).
    n (float): Nonlinearity exponent (default: 1, adjust based on empirical data).
    avg_RH (float): Default average humidity percentage (default: 50%).

    Returns:
    float: Fractional cloud cover (0 to 1)
    """
    # If RH is -1, use the average value
    if RH == -1:
        RH = avg_RH

    # Estimate clear sky temperature dynamically based on ambient temperature
    # Empirical estimate: Clear sky is typically 20-30°C lower than ambient on dry nights
    # Correction factor based on humidity
    clear_sky_offset = -20 + (RH / 10)  # More humid air reduces cooling effect
    T_clear_C_dynamic = T_ambient_C + clear_sky_offset
    
    # Boundaries check
    if T_sky_C <= T_clear_C_dynamic:
        return 0.0  # Fully clear sky
    elif T_sky_C >= T_cloud_C:
        return 1.0  # Fully overcast sky

    # Compute nonlinear cloud fraction
    return ((T_sky_C - T_clear_C_dynamic) / (T_cloud_C - T_clear_C_dynamic)) ** n

        # =============================================================================
        #         Note site_in_automatic found in the Enclosure object.
        # =============================================================================

        # if self.hostname in self.config["wema_hostname"]:

        #     self.is_wema = True
        #     self.is_process = False
        # else:
        #     self.is_wema = False
        #     self.is_process = True

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
    
        # self.rain_limit_setting = self.config['rain_limit']
        # self.humidity_limit_setting = self.config['humidity_limit']
        # self.windspeed_limit_setting = self.config['windspeed_limit']
        # self.lightning_limit_setting = self.config['lightning_limit']
        # self.temp_minus_dew_setting = self.config['temperature_minus_dewpoint_limit']
        # self.sky_temp_limit_setting = self.config['sky_temperature_limit']
        # self.cloud_cover_limit_setting = self.config['cloud_cover_limit']
        # self.lowest_temperature_setting = self.config['lowest_ambient_temperature']
        # self.highest_temperature_setting = self.config['highest_ambient_temperature']

        # self.warning_rain_limit_setting = self.config['warning_rain_limit']
        # self.warning_humidity_limit_setting = self.config['warning_humidity_limit']
        # self.warning_windspeed_limit_setting = self.config['warning_windspeed_limit']
        # self.warning_lightning_limit_setting = self.config['warning_lightning_limit']
        # self.warning_temp_minus_dew_setting = self.config['warning_temperature_minus_dewpoint_limit']
        # self.warning_sky_temp_limit_setting = self.config['warning_sky_temperature_limit']
        # self.warning_cloud_cover_limit_setting = self.config['warning_cloud_cover_limit']
        # self.warning_lowest_temperature_setting = self.config['warning_lowest_ambient_temperature']
        # self.warning_highest_temperature_setting = self.config['warning_highest_ambient_temperature']

        # self.rain_limit_on = self.config['rain_limit_on']
        # self.humidity_limit_on = self.config['humidity_limit_on']
        # self.windspeed_limit_on = self.config['windspeed_limit_on']
        # self.lightning_limit_on = self.config['lightning_limit_on']
        # self.temp_minus_dew_on = self.config['temperature_minus_dewpoint_limit_on']
        # self.sky_temperature_limit_on = self.config['sky_temperature_limit_on']
        # self.cloud_cover_limit_on = self.config['cloud_cover_limit_on']
        # self.lowest_temperature_on = self.config['lowest_ambient_temperature_on']
        # self.highest_temperature_on = self.config['highest_ambient_temperature_on']
        
        
# This is purely generic code for a generic site.
# It may be overwritten with a monkey patch found in the appropriate config.py.

#breakpoint()


# if not self.is_wema: #and self.site_is_custom:  # EG., this was written first for SRO.                                        #  system is a proxoy for having a WEMA
#     # This is NOT the normal ARO path
#     if self.config["site_IPC_mechanism"] == "shares":
#         try:
#             weather = open(g_dev["wema_share_path"] + "weather.txt", "r")
#             status = json.loads(weather.readline())
#             weather.close()
#             self.status = status
#             self.prior_status = status
#             g_dev["ocn"].status = status
#             return status
#         except:
#             try:
#                 time.sleep(3)
#                 weather = open(g_dev["wema_share_path"] + "weather.txt", "r")
#                 status = json.loads(weather.readline())
#                 weather.close()
#                 self.status = status
#                 self.prior_status = status
#                 g_dev["ocn"].status = status
#                 return status
#             except:
#                 try:
#                     time.sleep(3)
#                     weather = open(
#                         g_dev["wema_share_path"] + "weather.txt", "r"
#                     )
#                     status = json.loads(weather.readline())
#                     weather.close()
#                     self.status = status
#                     self.prior_status = status
#                     g_dev["ocn"].status = status
#                     return status
#                 except:
#                     plog("Using prior OCN status after 4 failures.")
#                     g_dev["ocn"].status = self.prior_status
#                     return self.prior_status

 cloud_percentage = calculate_cloud_fraction(weather_data['clouds'], weather_data['temp'],weather_data['hum'])
 #print(f"Estimated fractional cloud cover: {cloud_fraction:.2f}")



                # print (status)
                # breakpoint()
                   #Adding in necessary "ok to open" stuff for the status evaluation

                # rain_limit_setting = self.config['rain_limit']
                # humidity_limit_setting = self.config['humidity_limit']
                # windspeed_limit_setting = self.config['windspeed_limit']
                # temp_minus_dew_setting = self.config['temperature_minus_dewpoint_limit']
                # sky_temp_limit_setting = self.config['sky_temperature_limit']
                # cloud_cover_limit_setting = self.config['cloud_cover_limit']
                # lowest_temperature_setting = self.config['lowest_ambient_temperature']
                # highest_temperature_setting = self.config['highest_ambient_temperature']

                # wx_reasons = []
                # dewpoint_gap = False
                # rain_gap = False
                # temp_gap= False
                # humidity_gap = False
                # sky_gap = False
                # wind_gap = False
                # cloud_gap = False
                # self.gust_memory *= self.config['gust_decay_rate']
                # plog('(decaying) Gust:  ', round(self.gust_memory, 2))



                # if self.rain_rate in ['Wet', 'Raining']:  #Should we add Unl to this list?
                #     plog("Rain condition is:  ", self.rain_rate)
                #     wx_reasons.append('Rain > Dry')
                #     rain_gap = True
                # if self.humidity > humidity_limit_setting:
                #     wx_reasons.append('Humidity >= ' + str(humidity_limit_setting) + '%')
                #     humidity_gap = True
                # if max(self.windspeed, self.gust_memory) > windspeed_limit_setting:
                #     wx_reasons.append('Wind or Gust > ' + str(windspeed_limit_setting) + ' km/h')
                #     wind_gap = True
                # if (self.temperature - self.dewpoint) < temp_minus_dew_setting:
                #     wx_reasons.append('Ambient - Dewpoint < ' + str(temp_minus_dew_setting)
                #                      + 'C')
                #     dewpoint_gap = True
                # if self.sky_minus_ambient > sky_temp_limit_setting :
                #     wx_reasons.append('(sky - amb) > ' + str(sky_temp_limit_setting) + 'C')

                # try:
                #     #breakpoint()
                #     cloud_cover_value = float(self.sky_monitor.CloudCover)
                #     status['cloud_cover_%'] = round(cloud_cover_value, 0)
                #     if cloud_cover_value <= cloud_cover_limit_setting:
                #         cloud_cover = False
                #     else:
                #         cloud_cover = True
                #         wx_reasons.append('>=' + str(cloud_cover_limit_setting) + '% Cloudy')
                # except:
                #     status['cloud_cover_%'] = "no report"
                #     cloud_cover = True  # We cannot use this signal to force a wX hold or close
                # self.current_ambient = round(self.temperature, 2)
                # temp_bounds = lowest_temperature_setting < self.sky_monitor.Temperature < highest_temperature_setting

                # if not temp_bounds:

                #     wx_reasons.append('amb temp out of range')

                # self.wx_is_ok = not (
                #     dewpoint_gap
                #     or temp_gap
                #     or wind_gap
                #     or sky_gap
                #     or humidity_gap
                #     or rain_gap
                #     or cloud_gap
                # )
                # #  NB wx_is_ok does not include ambient light or altitude of the Sun
                # # the notion of Obs OK should bring in Sun Elevation and or ambient light.

                # #     if self.sky_monitor.RainRate > 0.0:
                # #         if self.sky_monitor.RainRate == 1:
                # #             # plog("%$%^%#^$%#*!$^#%$*@#^$%*@#^$%*#%$^&@#$*@&")
                # #             # plog("Rain Rate is 1.0")
                # #             # # plog('Rain > ' + str(rain_limit_setting))
                # #             # plog("This is usually a glitch so ignoring. Higher rain rates will trigger roof.")
                # #             # plog("%$%^%#^$%#*!$^#%$*@#^$%*@#^$%*#%$^&@#$*@&")
                # #             plog("Rain Flag is 1: This is usually a glitch so ignoring.")
                # #             plog("May be unevaporated rain, ice, or a bird dropping.")
                # #         else:
                # #             plog ("Rain rate is currently above 1. Saying that it is not ok.")
                # #             self.wx_is_ok=False

                # if self.wx_is_ok:
                #     wx_str = "Yes"
                #     status["wx_ok"] = "Yes"
                #     # plog('Wx Ok?  ', status["wx_ok"])
                # else:
                #     wx_str = "No"  # Ideally we add the dominant reason in priority order.
                #     status["wx_ok"] = "No"
                #     plog('Wx Ok: ', status["wx_ok"], wx_reasons)

                # g_dev["wx_ok"] = self.wx_is_ok
                
                
                # wx_reasons = []
                # #breakpoint()
                # rain_limit = self.sky_monitor.RainRate > self.rain_limit_setting
                # if rain_limit:
                #     plog("Reported rain rate in mm/hr:  ", self.sky_monitor.RainRate)
                #     wx_reasons.append('Rain > ' + str(self.rain_limit_setting))
                # humidity_limit = self.sky_monitor.Humidity < self.humidity_limit_setting
                # if not humidity_limit:
                #     wx_reasons.append('Humidity >= ' + str(self.humidity_limit_setting) + '%')

                # wind_limit = (
                #         self.sky_monitor.WindSpeed*0.2778 < self.windspeed_limit_setting
                # )  # sky_monitor reports km/h, Clarity may report in MPH
                # if not wind_limit:
                #     wx_reasons.append('Wind > ' + str(self.windspeed_limit_setting) + ' km/h')
                # dewpoint_gap = (
                #     not (self.sky_monitor.Temperature - self.sky_monitor.DewPoint) < self.temp_minus_dew_setting
                # )
                # if not dewpoint_gap:
                #     wx_reasons.append('Ambient - Dewpoint < ' + str(self.temp_minus_dew_setting) + 'C')
                # sky_amb_limit = (
                #                         self.sky_monitor.SkyTemperature - self.sky_monitor.Temperature
                #                 ) < self.sky_temp_limit_setting  # NB THIS NEEDS ATTENTION, Sky alert defaults to -17
                # if not sky_amb_limit:
                #     wx_reasons.append('(sky - amb) > ' + str(self.sky_temp_limit_setting) + 'C')
                # try:
                #     cloud_cover_value = float(self.sky_monitor.CloudCover)
                #     status['cloud_cover_%'] = round(cloud_cover_value, 0)
                #     if cloud_cover_value <= self.cloud_cover_limit_setting:
                #         cloud_cover = False
                #     else:
                #         cloud_cover = True
                #         wx_reasons.append('>=' + str(self.cloud_cover_limit_setting) + '% Cloudy')
                # except:
                #     status['cloud_cover_%'] = "no report"
                #     cloud_cover = True  # We cannot use this signal to force a wX hold or close
                # self.current_ambient = round(self.temperature, 2)
                # temp_bounds = self.lowest_temperature_setting < self.sky_monitor.Temperature < self.highest_temperature_setting

                # if not temp_bounds:
                #     wx_reasons.append('amb temp out of range')

                # self.wx_is_ok = (
                #         (dewpoint_gap and self.temp_minus_dew_on)
                #         and (temp_bounds and (self.lowest_temperature_on or self.highest_temperature_on))
                #         and (wind_limit and self.windspeed_limit_on)
                #         and (sky_amb_limit and self.sky_temperature_limit_on)
                #         and (humidity_limit and self.humidity_limit_on)
                #         and not (rain_limit and self.rain_limit_on)
                #         and not (cloud_cover and self.cloud_cover_limit_on)
                # )
                # #  NB wx_is_ok does not include ambient light or altitude of the Sun
                # # the notion of Obs OK should bring in Sun Elevation and or ambient light.

                # if self.sky_monitor.RainRate > 0.0:
                #     #plog("%$%^%#^$%#*!$^#%$*@#^$%*@#^$%*#%$^&@#$*@&")
                #     #plog("Rain Rate is 1.0")
                #     # plog('Rain > ' + str(rain_limit_setting))
                #     plog("Rain Flag is 1: This is usually a glitch so ignoring.")
                #     plog("May be unevaporated rain, ice, or a bird dropping.")
                #     #plog("%$%^%#^$%#*!$^#%$*@#^$%*@#^$%*#%$^&@#$*@&")

                # if self.wx_is_ok:
                #     wx_str = "Yes"
                #     status["wx_ok"] = "Yes"
                #     # plog('Wx Ok?  ', status["wx_ok"])
                # else:
                #     wx_str = "No"  # Ideally we add the dominant reason in priority order.
                #     status["wx_ok"] = "No"
                #     plog('Wx Ok: ', status["wx_ok"], wx_reasons)

                # g_dev["wx_ok"] = self.wx_is_ok
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
    
    
            #  NB wx_is_ok does not include ambient light or altitude of the Sun
            # the notion of Obs OK should bring in Sun Elevation and or ambient light.
            
            #breakpoint()
    
            # if quick_status['rain_rate']> 0.0:
            #     #plog("%$%^%#^$%#*!$^#%$*@#^$%*@#^$%*#%$^&@#$*@&")
            #     #plog("Rain Rate is 1.0")
            #     # plog('Rain > ' + str(rain_limit_setting))
            #     plog("For SkyAlerts: Rain Flag is 1: This is usually a glitch so ignoring.")
            #     plog("May be unevaporated rain, ice, or a bird dropping.")
            #     #plog("%$%^%#^$%#*!$^#%$*@#^$%*@#^$%*#%$^&@#$*@&")
            
            
            # def update_enclosure_immediately(self, enc_status):
                
            #     lane = "enclosure"
            #     plog ("updating enclosure immediately")
            #     wema = self.config['wema_name']  
            #     try:                        
            #         send_status(wema, lane, enc_status)
            #     except:
            #         plog('could not send enclosure status')   
            #         plog(traceback.format_exc())
            
            
            
                #breakpoint()
                # if ocn_status==None:
                #     self.local_weather_ok = None
                # else:
                   
                #     if 'wx_ok' in ocn_status:
                #         if ocn_status['wx_ok'] == 'Yes':
                #             self.local_weather_ok = True
                #         elif ocn_status['wx_ok'] == 'No':
                #             self.local_weather_ok = False
                #         else:
                #             self.local_weather_ok = None
                #     else:
                #         self.local_weather_ok = None