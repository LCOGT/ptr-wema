"""
WER 20210624

First attempt at having a parallel dedicated agent for weather and enclosure.
This code should be as simple and reliable as possible, no hanging variables,
etc.

This would be a good place to log the weather data and any enclosure history,
once this code is stable enough to run as a service.

We need to resolve the 'redis' solution for each site. 20210826

Note this is derived from OBS but is WEMA so we should not need to build
things from a config file, but rather by implication just pick the correct
data from the config file. All config files for a cluster of mounts/telescopes
under one WEMA should start with common data for the WEMA. Note the WEMA
has no knowledge of how many mnt/tels there may be in any given enclosure.
"""


import os
import signal
import json
import shelve
import time
import socket
from pathlib import Path
import math
import requests
import redis
import datetime
import traceback

import ptr_config
from api_calls import API_calls
import wema_events
from devices.observing_conditions import ObservingConditions
from devices.enclosure import Enclosure
from global_yard import g_dev
from wema_utility import plog
from pyowm import OWM
from pyowm.utils import config
from pyowm.utils import timestamps

# FIXME: This needs attention once we figure out the restart_obs script.
def terminate_restart_observer(site_path, no_restart=False):
    """Terminates observatory code if running and restarts obs."""
    if no_restart is False:
        return

    camShelf = shelve.open(site_path + "ptr_night_shelf/" + "pid_obs")
    pid = camShelf["pid_obs"]  # a 9 character string
    camShelf.close()
    try:
        print("Terminating:  ", pid)
        os.kill(pid, signal.SIGTERM)
    except:
        print("No observer process was found, starting a new one.")
    # The above routine does not return but does start a process.
    parentPath = Path.cwd()
    os.system("cmd /c " + str(parentPath) + "\restart_obs.bat")

    return


def send_status(obsy, column, status_to_send):
    """Sends a status update to AWS."""
    
    uri_status = f"https://status.photonranch.org/status/{obsy}/status/"
    # NB None of the strings can be empty. Otherwise this put faults.
    payload = {"statusType": str(column), "status": status_to_send}
    data = json.dumps(payload)
    try:
        response = requests.post(uri_status, data=data)

    #if response.ok:
       # pass
       # print("Status sent successfully.")
    except:
        print(
            'self.api.authenticated_request("PUT", uri, status):  Failed! ',
            response.status_code,
        )

class WxEncAgent:
    """A class for weather enclosure functionality."""

    def __init__(self, name, config):

        self.api = API_calls()
        self.command_interval = 30
        self.status_interval = 30
        self.config = config
        g_dev["obs"] = self
        g_dev['debug'] = False
       
        # self.debug_flag = self.config['debug_mode']
        # self.admin_only_flag = self.config['admin_owner_commands_only']
        # if self.debug_flag:
        #     self.debug_lapse_time = time.time() + self.config['debug_duration_sec']
        #     g_dev['debug'] = True
        #     #g_dev['obs'].open_and_enabled_to_observe = True
        # else:
        #     self.debug_lapse_time = 0.0
        #     g_dev['debug'] = False
        #     #g_dev['obs'].open_and_enabled_to_observe = False



        #self.hostname = self.hostname = socket.gethostname()
        if self.hostname in self.config["wema_hostname"]:
            self.is_wema = True
            self.is_process = False

        self.site = config["site"]
        self.debug_flag = self.config['debug_site_mode']
        self.admin_only_flag = self.config['admin_owner_commands_only']
        if self.debug_flag:
            self.debug_lapse_time = time.time() + self.config['debug_duration_sec']
            g_dev['debug'] = True
            #g_dev['obs'].open_and_enabled_to_observe = True
        else:
            self.debug_lapse_time = 0.0
            g_dev['debug'] = False
            #g_dev['obs'].open_and_enabled_to_observe = False

        if self.config["wema_is_active"]:
            self.hostname = self.hostname = socket.gethostname()
            if self.hostname in self.config["wema_hostname"]:
                self.is_wema = True
                g_dev["wema_write_share_path"] = config["wema_write_share_path"]
                self.wema_path = g_dev["wema_write_share_path"]
                self.site_path = self.wema_path
            else:
                # This host is a client
                self.is_wema = False  # This is a client.
                self.site_path = config["wema_write_share_path"]
                g_dev["site_path"] = self.site_path
                g_dev["wema_write_share_path"] = self.site_path  # Just to be safe.
                self.wema_path = g_dev["wema_write_share_path"]
        else:
            # This host is a client
            self.is_wema = False  # This is a client.
            self.is_process = True


            self.site_path = config["client_write_share_path"]
            g_dev["site_path"] = self.site_path
            g_dev["wema_write_share_path"] = self.site_path  # Just to be safe.
            self.wema_path = g_dev["wema_write_share_path"]

        if self.config["site_is_custom"]:
            self.site_is_custom = True
        else:
            self.site_is_custom = False

        self.last_request = None
        self.stopped = False
        self.site_message = "-"
        self.site_mode = config['site_enclosure_default_mode']
        self.device_types = config["wema_types"]
        self.astro_events = wema_events.Events(self.config)
        self.astro_events.compute_day_directory()
        self.astro_events.calculate_events()
        self.astro_events.display_events()

        self.wema_pid = os.getpid()
        print("WEMA_PID:  ", self.wema_pid)

        # if config["redis_ip"] is not None:
        #     self.redis_server = redis.StrictRedis(
        #         host=config["redis_ip"], port=6379, db=0, decode_responses=True
        #     )
        #     self.redis_wx_enabled = True
        #     # Enable wide easy access to this object with redis.
        #     g_dev["redis"] = self.redis_server
        #     for key in self.redis_server.keys():
        #         self.redis_server.delete(key)  # Flush old state.
        #     self.redis_server.set("wema_pid", self.wema_pid)
        # else:
        #self.redis_wx_enabled = False
        #g_dev["redis"] = None
        #  g_dev['redis_server']['wema_loaded'] = True

        # Here we clean up any older processes
        # prior_wema = self.redis_server.get("wema_pid")
        # prior_obs = self.redis_server.get("obs_pid")

        # if prior_wema is not None:
        #     pid = int( prior_wema)
        #     try:
        #         print("Terminating Wema:  ", pid)
        #         os.kill(pid, signal.SIGTERM)
        #     except:
        #         print("No wema process was found, starting a new one.")
        # if prior_obs is not None:
        #     pid = int( prior_obs)
        #     try:
        #         print("Terminating Obs:  ", pid)
        #         os.kill(pid, signal.SIGTERM)
        #     except:
        #         print("No observer process was found, starting a new one.")

        self.wema_pid = os.getpid()
        print("Fresh WEMA_PID:  ", self.wema_pid)
        self.update_config()
        self.create_devices(config)
        self.time_last_status = time.time() - 60  #forces early status on startup.
        self.loud_status = False
        self.blocks = None
        self.projects = None
        self.events_new = None
        immed_time = time.time()
        self.obs_time = immed_time
        self.wema_start_time = immed_time
        self.cool_down_latch = False
        # This variable prevents the roof being called to open every loop...
        self.enclosure_next_open_time = time.time()
        # This keeps a track of how many times the roof has been open this evening
        # Which is really a measure of how many times the observatory has
        # attempted to observe but been shut on....
        # If it is too many, then it shuts down for the whole evening.
        self.opens_this_evening = 0
        obs_win_begin, sunZ88Op, sunZ88Cl, ephem_now = self.astro_events.getSunEvents()
        self.weather_report_wait_until_open = False
        self.weather_report_wait_until_open_time = ephem_now
        self.weather_report_close_during_evening = False
        self.weather_report_close_during_evening_time = ephem_now + 86400
        self.nightly_weather_report_complete = False

        self.open_and_enabled_to_observe = False

        if not g_dev['debug']:
            #self.global_wx()

            self.run_nightly_weather_report()
        else:
            self.nightly_weather_report_complete = True
            self.weather_report_is_acceptable_to_observe = True
            self.weather_report_wait_until_open=False

        # self.global_wx()
        # breakpoint()
            
        # self.redis_server.set('obs_time', immed_time, ex=360)
        # terminate_restart_observer(g_dev['obs']['site_path'], no_restart=True)
        
# =============================================================================
#         # NB Inherited from MF work on Wx in Sequencer
#         
# =============================================================================
        # This variable prevents the roof being called to open every loop...        
        self.enclosure_next_open_time = time.time()
        # This keeps a track of how many times the roof has been open this evening
        # Which is really a measure of how many times the observatory has
        # attempted to observe but been shut on....
        # If it is too many, then it shuts down for the whole evening. 
        self.opens_this_evening = 0
        
        #self.morn_bias_done = False
        #self.eve_flats_done = False
        #self.morn_flats_done = False
        #self.eve_sky_flat_latch = False
        #self.morn_sky_flat_latch = False
        # The weather report has to be at least passable at some time of the night in order to 
        # allow the observatory to become active and observe. This doesn't mean that it is 
        # necessarily a GOOD night at all, just that there are patches of feasible
        # observing during the night.
        self.nightly_weather_report_complete = False
        self.weather_report_is_acceptable_to_observe = False
        # If the night is patchy, the weather report can identify a later time to open
        # or to close the observatory early during the night.
        obs_win_begin, sunZ88Op, sunZ88Cl, ephem_now = self.astro_events.getSunEvents()
        self.weather_report_wait_until_open=False
        self.weather_report_wait_until_open_time=ephem_now
        self.weather_report_close_during_evening=False
        self.weather_report_close_during_evening_time=ephem_now
        self.nightly_weather_report_done=False
        
        
        self.nightly_reset_complete = False
        
        
        # Run a weather report on bootup so observatory can run if need be. 
        self.run_nightly_weather_report()
        # if not g_dev['debug']:
        #     #self.global_wx()

        #     self.run_nightly_weather_report()
        # else:
        #     self.nightly_weather_report_complete = True
        #     self.weather_report_is_acceptable_to_observe = True
        #     self.weather_report_wait_until_open=True
            
        #NB End of inheritance
            #g_dev['obs'].open_and_enabled_to_observe = True
            
            #Consider running this once when in debug mode

    def create_devices(self, config: dict):
        self.all_devices = {}
        for (
            dev_type
        ) in self.device_types:  # This has been set up for wema to be ocn and enc.
            self.all_devices[dev_type] = {}
            devices_of_type = config.get(dev_type, {})
            device_names = devices_of_type.keys()
            if dev_type == "camera":
                pass
            for name in device_names:
                driver = devices_of_type[name]["driver"]
                # settings = devices_of_type[name].get("settings", {})

                if dev_type == "observing_conditions":

                    device = ObservingConditions(
                        driver, name, self.config, self.astro_events
                    )
                elif dev_type == "enclosure":
                    device = Enclosure(driver, name, self.config, self.astro_events)
                else:
                    print(f"Unknown device: {name}")
                self.all_devices[dev_type][name] = device
        print("Finished creating devices.")

    def update_config(self):
        """Sends the config to AWS."""

        uri = f"{self.config['wema_name']}/config/"
        self.config["events"] = g_dev["events"]

        response = self.api.authenticated_request("PUT", uri, self.config)
        if response:
            print("\n\nConfig uploaded successfully.")

    def scan_requests(self, mount):
        """
        
        This can pick up owner/admin Shutdown and Automatic request but it 
        would need to be a custom api endpoint.
        
        Not too many useful commands: Shutdown, Automatic, Immediate close,
        BadWxSimulate event (ie a 15 min shutdown)

        For a wema this can be used to capture commands to the wema once the
        AWS side knows how to redirect from any mount/telescope to the common
        Wema.
        This should be changed to look into the site command queue to pick up
        any commands directed at the Wx station, or if the agent is going to
        always exist lets develop a seperate command queue for it.
        """
        return

    def update_status(self):
        """
        Collect status from weather and enclosure devices and sends an
        update to AWS. Each device class is responsible for implementing the
        method 'get_status()', which returns a dictionary.
        """

        loud = False
        while time.time() < self.time_last_status + self.status_interval:
            return
        #t1 = time.time()
        status = {}

        for dev_type in self.device_types:
            status[dev_type] = {}
            devices_of_type = self.all_devices.get(dev_type, {})
            device_names = devices_of_type.keys()
            for device_name in device_names:
                device = devices_of_type[device_name]

                status[dev_type][device_name] = device.get_status()

        # Include the time that the status was assembled and sent.
        status["timestamp"] = round(time.time(), 1)
        #status["send_heartbeat"] = False   #This has never been implemented.
        enc_status = None
        ocn_status = None
        device_status = None
        obsy = self.config['wema_name']   #  This is meant to be for the site, not an OBSP.

        try:

            ocn_status = {"observing_conditions": status.pop("observing_conditions")}
            enc_status = {"enclosure": status.pop("enclosure")}
            device_status = status
        except:
            pass
        
        ## NB We should consolidate this into one *site* status tranaction. WER 20230617


        if ocn_status is not None:
            lane = "weather"
            #send_status(obsy, lane, ocn_status)  # Do not remove this send for SAF!
            if ocn_status is not None:
                lane = "weather"
                
                try:
                    send_status(obsy, lane, ocn_status)
                except:
                    time.sleep(10)
                    try:
                        send_status(obsy, lane, ocn_status)
                    except:
                        time.sleep(10)
                        try:
                            send_status(obsy, lane, ocn_status)
                        except:
                            plog("Three Tries to send Wx status for MRC failed.")
        if enc_status is not None:
            lane = "enclosure"
            #send_status(obsy, lane, enc_status)
            try:
                time.sleep(2)
                send_status(obsy, lane, enc_status)
            except:
                time.sleep(10)
                try:
                    send_status(obsy, lane, enc_status)
                except:
                    time.sleep(10)
                    try:
                        send_status(obsy, lane, enc_status)
                    except:
                        plog("Three Tries to send Enc status for MRC2 failed.")
            #if self.name == "mrc":   #NB  This does not scale, Wema config should has a list of sub-sites.
            #    obsy = 'mrc2'        #  or have AWS pick up status from the wema only.
            if ocn_status is not None:
                lane = "weather"
                
                try:
                    time.sleep(2)
                    send_status(obsy, lane, ocn_status)
                except:
                    time.sleep(10)
                    try:
                        send_status(obsy, lane, ocn_status)
                    except:
                        time.sleep(10)
                        try:
                            send_status(obsy, lane, ocn_status)
                        except:
                            plog("Three Tries to send Wx status for MRC2 failed.")
                    

            if enc_status is not None:
                lane = "enclosure"
                try:
                    time.sleep(2)
                    send_status(obsy, lane, enc_status)
                except:
                    time.sleep(10)
                    try:
                        send_status(obsy, lane, enc_status)
                    except:
                        time.sleep(10)
                        try:
                            send_status(obsy, lane, enc_status)
                        except:
                            plog("Three Tries to send Enc status for MRC2 failed.")

        loud = False
        if loud:
            print("\n\n > Status Sent:  \n", status)


        #else:

        # try:    #This needs some sort of rework, redis generally not deployed
        #     obs_time = float(self.redis_server.get("obs_time"))
        #     delta = time.time() - obs_time
        # except:
        #     delta = 999.99  # NB Temporarily flags something really wrong.


        # if delta > 1800:
        #     print(">The observer's time is stale > 300 seconds:  ", round(delta, 2))
        # # Here is where we terminate the obs.exe and restart it.
        # if delta > 3600:
        #     # terminate_restart_observer(g_dev['obs'}['site_path'], no_restart=True)
        #     pass
        # else:
        #     print(">")

    def update(self):     ## NB NB NB This is essentially the sequencer for the WEMA.
        self.update_status()
        time.sleep(15)

        # Here it runs through the various checks and decides whether to open or close the roof or not.
        # Check for delayed opening of the observatory and act accordingly.

        # If the observatory is simply delayed until opening, then wait until then, then attempt to start up the observatory
        obs_win_begin, sunZ88Op, sunZ88Cl, ephem_now = self.astro_events.getSunEvents()

        #breakpoint()
        ocn_status = g_dev['ocn'].get_status()
        enc_status = g_dev['enc'].get_status()

        #breakpoint()
        plog("***************************************************************")
        plog("Current time             : " + str(time.asctime()))
        plog("Shutter Status           : " + str(enc_status['shutter_status']))
        if ocn_status == None:
            plog("This WEMA does not report observing conditions")
        else:
            plog("Observing Conditions      : " +str(ocn_status))
        if enc_status['enclosure_mode'] == 'Manual':
            plog ("Weather Report overriden due to being in Manual or debug mode.")
        else:
            plog("Weather Report Good to Observe: " + str(self.weather_report_is_acceptable_to_observe))
        plog("Time until Cool and Open      : " + str(round(( g_dev['events']['Cool Down, Open'] - ephem_now) * 24,2)) + " hours")
        plog("Time until Close and Park     : "+ str(round(( g_dev['events']['Close and Park'] - ephem_now) * 24,2)) + " hours")
        plog("**************************************************************")

        #breakpoint()

        # Safety checks here

        if not g_dev['debug'] and self.open_and_enabled_to_observe:
            if enc_status is not None:
                if enc_status['shutter_status'] == 'Software Fault':
                    plog("Software Fault Detected. Will alert the authorities!")
                    #plog("Parking Scope in the meantime")
                    # if self.config['obsid_roof_control'] and g_dev['enc'].mode == 'Automatic':
                    self.open_and_enabled_to_observe = False
                    self.park_enclosure_and_close()
                    #self.cancel_all_activity()  # NB THis kills bias-dark
                   # if not g_dev['mnt'].mount.AtPark:
                    #    if g_dev['mnt'].home_before_park:
                    #        g_dev['mnt'].home_command()
                    #    g_dev['mnt'].park_command()
                    # will send a Close call out into the blue just in case it catches
                    # g_dev['enc'].enclosure.CloseShutter()
                    # g_dev['seq'].enclosure_next_open_time = time.time(
                    # ) + self.config['roof_open_safety_base_time'] * g_dev['seq'].opens_this_evening

                if enc_status['shutter_status'] == 'Closing':
                    # if self.config['obsid_roof_control'] and g_dev['enc'].mode == 'Automatic':
                    plog("Detected Roof Closing.")
                    self.open_and_enabled_to_observe = False
                    self.park_enclosure_and_close()

                    self.enclosure_next_open_time = time.time(
                     ) + self.config['roof_open_safety_base_time'] * self.opens_this_evening

                if enc_status['shutter_status'] == 'Error':
                    if  enc_status['enclosure_mode'] == 'Automatic':
                        plog("Detected an Error in the Roof Status. Packing up for safety.")
                        self.open_and_enabled_to_observe = False
                        self.park_enclosure_and_close()
                        self.enclosure_next_open_time = time.time(
                        ) + self.config['roof_open_safety_base_time'] * self.opens_this_evening

                        # plog("This is usually because the weather system forced the roof to shut.")
                        # plog("By closing it again, it resets the switch to closed.")
                        #self.cancel_all_activity()  # NB Kills bias dark
                        #self.open_and_enabled_to_observe = False
                        # g_dev['enc'].enclosure.CloseShutter()
                        # g_dev['seq'].enclosure_next_open_time = time.time(
                        # ) + self.config['roof_open_safety_base_time'] * g_dev['seq'].opens_this_evening
                        # while g_dev['enc'].enclosure.ShutterStatus == 3:
                        # plog ("closing")
                        #plog("Also Parking the Scope")
                        #if not g_dev['mnt'].mount.AtPark:
                        #    if g_dev['mnt'].home_before_park:
                        #        g_dev['mnt'].home_command()
                        #    g_dev['mnt'].park_command()

                # roof_should_be_shut = False
            else:
                plog("Enclosure roof status probably not reporting correctly. WEMA down?")

        roof_should_be_shut = False

        if not (g_dev['events']['Cool Down, Open'] < ephem_now < g_dev['events']['Close and Park']):
            roof_should_be_shut = True
            self.open_and_enabled_to_observe = False

        if enc_status['shutter_status'] == 'Open':
            if roof_should_be_shut == True:
                plog("Safety check notices that the roof was open outside of the normal observing period")
                self.park_enclosure_and_close()

        if (self.enclosure_next_open_time - time.time()) > 0:
            plog("opens this eve: " + str(self.opens_this_evening))

            plog("minutes until next open attempt ALLOWED: " +
                 str((self.enclosure_next_open_time - time.time()) / 60))

        if self.weather_report_wait_until_open and not self.cool_down_latch:
            if ephem_now > self.weather_report_wait_until_open_time:

                self.cool_down_latch = True
                self.weather_report_wait_until_open == False
                # Things may have changed! So re-checking the weather and such

                # Reopening config and resetting all the things.
                # This is necessary just in case a previous weather report was done today
                # That can sometimes change the timing.
                self.astro_events.compute_day_directory()
                self.astro_events.calculate_events()
                # self.astro_events.display_events()
                #g_dev['obs'].astro_events = self.astro_events
                # Run nightly weather report
                self.run_nightly_weather_report()

                if not self.open_and_enabled_to_observe and self.weather_report_is_acceptable_to_observe == True:
                    if (g_dev['events']['Cool Down, Open'] < ephem_now < g_dev['events']['Observing Ends']):
                        if time.time() > self.enclosure_next_open_time and self.opens_this_evening < self.config[
                            'maximum_roof_opens_per_evening']:
                            # self.enclosure_next_open_time = time.time() + 300 # Only try to open the roof every five minutes
                            self.nightly_reset_complete = False
                            # self.weather_report_is_acceptable_to_observe=True
                            self.open_observatory(enc_status, ocn_status)

                            # If the observatory opens, set clock and auto focus and observing to now
                            if self.open_and_enabled_to_observe:
                                #self.weather_report_is_acceptable_to_observe = False
                                #obs_win_begin, sunZ88Op, sunZ88Cl, ephem_now = self.astro_events.getSunEvents()
                                # g_dev['events']['Clock & Auto Focus'] = ephem_now - 0.1/24
                                # g_dev['events']['Observing Begins'] = ephem_now + 0.1/24
                                self.weather_report_wait_until_open = False
                                self.weather_report_is_acceptable_to_observe = True
                                
                self.cool_down_latch = False

        # If the observatory is meant to shut during the evening
        obs_win_begin, sunZ88Op, sunZ88Cl, ephem_now = self.astro_events.getSunEvents()
        if self.weather_report_close_during_evening == True:
            if ephem_now > self.weather_report_close_during_evening_time and ephem_now < g_dev['events'][
                'Close and Park']:  
                if enc_status['enclosure_mode'] == 'Automatic':
                    self.nightly_reset_complete = False
                    self.weather_report_is_acceptable_to_observe = False
                    plog("End of Observing Period due to weather. Closing up observatory early.")
                    
                    self.open_and_enabled_to_observe = False
                    self.park_enclosure_and_close()

                    self.weather_report_close_during_evening = False

                    # Do nightly weather report at cool down open
        if (g_dev['events']['Cool Down, Open'] <= ephem_now < g_dev['events'][
            'Observing Ends']) and not self.nightly_weather_report_complete and not g_dev['debug']:
            # Reopening config and resetting all the things.
            # This is necessary just in case a previous weather report was done today
            # That can sometimes change the timing.
            #self.astro_events.compute_day_directory()
            #self.astro_events.calculate_events()
            # self.astro_events.display_events()
            #g_dev['obs'].astro_events = self.astro_events
            # Run nightly weather report
            self.run_nightly_weather_report()
            self.nightly_weather_report_complete = True

            # Also make sure nightly reset is switched to go off
            self.nightly_reset_complete = False
            # As well as nightly focus routine.
            self.night_focus_ready = True



        if ((g_dev['events']['Cool Down, Open'] <= ephem_now < g_dev['events']['Observing Ends']) and \
            enc_status['enclosure_mode'] == 'Automatic') and not self.cool_down_latch and not g_dev['ocn'].wx_hold and not \
            enc_status['shutter_status'] in ['Software Fault', 'Closing', 'Error']:

            self.cool_down_latch = True

            if not self.open_and_enabled_to_observe and self.weather_report_is_acceptable_to_observe == True and self.weather_report_wait_until_open == False:

                if time.time() > self.enclosure_next_open_time and self.opens_this_evening < self.config['maximum_roof_opens_per_evening']:
                    self.nightly_reset_complete = False
                    # self.enclosure_next_open_time = time.time() + 300 # Only try to open the roof every five minutes maximum
                    self.open_observatory(enc_status, ocn_status)

            self.cool_down_latch = False

        # If in post-close and park era of the night, check those two things have happened!
        if (g_dev['events']['Close and Park'] <= ephem_now < g_dev['events']['Nightly Reset']) \
                and enc_status['enclosure_mode'] == 'Automatic':

            if not enc_status['shutter_status'] in ['Closed', 'closed']:
                plog("Found shutter open after Close and Park, shutting up the shutter")
                self.park_enclosure_and_close()
        
        
        if (g_dev['events']['Nightly Reset'] <= ephem_now < g_dev['events']['End Nightly Reset']): # and g_dev['enc'].mode == 'Automatic' ):
            
            if self.nightly_reset_complete == False:
                self.nightly_reset_script()

    def nightly_reset_script(self):
        # UNDERTAKING END OF NIGHT ROUTINES

        # Never hurts to make sure the telescope is parked for the night
        #g_dev['mnt'].park_command({}, {})
        #self.park_and_close(enc_status = g_dev['enc'].status)   #WEMA does not control telescopes.

        self.park_enclosure_and_close()

        self.nightly_weather_report_complete=False
        # Set weather report to false because it is daytime anyways.
        self.weather_report_is_acceptable_to_observe=False
        
        
        
        # Trying to figure out why sequencer isn't restarting.
        events = g_dev['events']
        obs_win_begin, sunZ88Op, sunZ88Cl, ephem_now = self.astro_events.getSunEvents()

        # Reopening config and resetting all the things.
        self.astro_events.compute_day_directory()
        self.astro_events.calculate_events()
        self.astro_events.display_events()
        #g_dev['obs'].astro_events = self.astro_events
        
        
        # sending this up to AWS
        '''
        Send the config to aws.
        '''
        uri = f"{self.config['wema_name']}/config/"
        self.config['events'] = g_dev['events']
        response = self.api.authenticated_request("PUT", uri, self.config)
        if response:
            plog("Config uploaded successfully.")

        self.cool_down_latch = False
        
        
        self.nightly_reset_complete = True
        
        self.opens_this_evening=0
        
        # Set weather report back to False until ready to check the weather again. 
        self.nightly_weather_report_complete=False
        self.weather_report_is_acceptable_to_observe=False
        self.weather_report_wait_until_open=False
        self.weather_report_wait_until_open_time=ephem_now
        self.weather_report_close_during_evening=False
        self.weather_report_close_during_evening_time=ephem_now + 86400
        self.nightly_weather_report_complete=False
        
        return



    def run(self):  # run is a poor name for this function.
        """Runs the continuous WEMA process.

        Loop ends with keyboard interrupt."""
        try:
            while True:
                self.update()  # `Ctrl-C` will exit the program.
        except KeyboardInterrupt:
            print("Finishing loops and exiting...")
            self.stopped = True
            return

    def send_to_user(self, p_log, p_level="INFO"):
        """ """
        url_log = "https://logs.photonranch.org/logs/newlog"
        body = json.dumps(
            {
                "site": self.config["site"],
                "log_message": str(p_log),
                "log_level": str(p_level),
                "timestamp": time.time(),
            }
        )
        try:
            response = requests.post(url_log, body)
        except Exception:
            print("Log did not send, usually not fatal.")

    def park_enclosure_and_close(self):
        
        g_dev['enc'].close_roof_directly({}, {})
        
        return

    def open_observatory(self, enc_status, ocn_status, no_sky=False):

        #if not self.config['obsid_roof_control']:
            # plog("A request to open observatory was made even though this platform has no roof control. Returning.")
        #    return

        flat_spot, flat_alt = g_dev['evnt'].flat_spot_now()
        obs_win_begin, sunZ88Op, sunZ88Cl, ephem_now = self.astro_events.getSunEvents()

        # Only send an enclosure open command if the weather
        if self.weather_report_is_acceptable_to_observe:

            if not g_dev['debug'] and not enc_status['enclosure_mode'] in ['Manual'] and (
                    ephem_now < g_dev['events']['Cool Down, Open']) or \
                    (g_dev['events']['Close and Park'] < ephem_now < g_dev['events']['Nightly Reset']):
                plog("NOT OPENING THE OBSERVATORY -- IT IS THE DAYTIME!!")
                self.send_to_user("An open observatory request was rejected as it is during the daytime.")
                return
            else:

                try:

                    plog("Attempting to open the roof.")

                    if ocn_status == None:
                        if not enc_status['shutter_status'] in ['Open', 'open','Opening','opening'] and \
                                enc_status['enclosure_mode'] == 'Automatic' \
                                and self.weather_report_is_acceptable_to_observe:
                            self.opens_this_evening = self.opens_this_evening + 1

                            g_dev['enc'].open_roof_directly({}, {})
                            # g_dev['enc'].open_command({}, {})


                    elif  not enc_status['shutter_status'] in ['Open', 'open','Opening','opening'] and \
                            enc_status['enclosure_mode'] == 'Automatic' \
                            and ocn_status['hold_duration'] <= 0.1  and self.weather_report_is_acceptable_to_observe:  # NB

                        self.opens_this_evening = self.opens_this_evening + 1

                        g_dev['enc'].open_roof_directly({}, {})
                        # g_dev['enc'].open_command({}, {})

                    plog("Attempting to Open Shutter. Waiting until shutter opens")
                    if not g_dev['enc'].enclosure.ShutterStatus == 0:
                        time.sleep(self.config['period_of_time_to_wait_for_roof_to_open'])

                    self.enclosure_next_open_time = time.time() + (self.config['roof_open_safety_base_time'] * 60) * self.opens_this_evening


                    if g_dev['enc'].enclosure.ShutterStatus == 0:
                        self.open_and_enabled_to_observe = True

                        try:
                            plog("Synchronising dome.")
                            g_dev['enc'].sync_mount_command({}, {})
                        except:
                            pass
                        # Prior to skyflats no dome following.
                        self.dome_homed = False

                        return

                    else:
                        plog("Failed to open roof, parking telescope again and sending the close command to the roof.")
                        # g_dev['enc'].close_roof_directly()
                        plog("opens this eve: " + str(self.opens_this_evening))
                        plog("minutes until next open attempt ALLOWED: " + str(
                            (self.enclosure_next_open_time - time.time()) / 60))
                        g_dev['enc'].close_roof_directly({}, {})

                        return

                except Exception as e:
                    plog("Enclosure opening glitched out: ", e)
                    plog(traceback.format_exc())

        else:
            plog("An enclosure command was rejected because the weather report was not acceptable.")

        return

    def run_nightly_weather_report(self):
       
        # g_dev['ocn'].status = g_dev['ocn'].get_status()
        # g_dev['enc'].status = g_dev['enc'].get_status()
        # ocn_status = g_dev['ocn'].status
        # enc_status = g_dev['enc'].status
        events = g_dev['events']
        
        obs_win_begin, sunset, sunrise, ephem_now = self.astro_events.getSunEvents()
        if self.nightly_weather_report_complete==False:
            
            # First thing to do at the Cool Down, Open time is to calculate the quality of the evening
            # using the broad weather report.
            try: 
                plog("Appraising quality of evening from Open Weather Map.")
                owm = OWM('d5c3eae1b48bf7df3f240b8474af3ed0')
                mgr = owm.weather_manager()            
                one_call = mgr.one_call(lat=self.config["latitude"], lon=self.config["longitude"])
                self.nightly_weather_report_complete=True
                
                # Collect relevant info for fitzgerald weather number calculation
                hourcounter=0
                fitzgerald_weather_number_grid=[]
                hours_until_end_of_observing= math.ceil((events['Observing Ends'] - ephem_now) * 24)
                plog("Hours until end of observing: " + str(hours_until_end_of_observing))
                
                
                for hourly_report in one_call.forecast_hourly:
                    
                    if hourcounter > hours_until_end_of_observing:
                        pass
                    else:
                        fitzgerald_weather_number_grid.append([hourly_report.humidity,hourly_report.clouds,hourly_report.wind()['speed'],hourly_report.status, hourly_report.detailed_status])
                        hourcounter=hourcounter + 1
                plog (fitzgerald_weather_number_grid)    
                
                
                # Fitzgerald weather number calculation.
                hourly_fitzgerald_number=[]
                for entry in fitzgerald_weather_number_grid:
                    tempFn=0
                    # Add humidity score up
                    if 80 < entry[0] <= 85:
                        tempFn=tempFn+1
                    elif 85 < entry[0] <= 90:
                        tempFn=tempFn+4
                    elif 90 < entry[0] <= 100:
                        tempFn=tempFn+40
                    
                    # Add cloud score up
                    if 20 < entry[1] <= 40:
                        tempFn=tempFn+1
                    elif 40 < entry[1] <= 60:
                        tempFn=tempFn+4
                    elif 60 < entry[1] <= 80:
                        tempFn=tempFn+40
                    elif 80 < entry[1] <= 100:
                        tempFn=tempFn+100
                    
                    # Add wind score up
                    if 8 < entry[2] <=12:
                        tempFn=tempFn+1
                    elif 12 < entry[2] <= 15:
                        tempFn=tempFn+4
                    elif 15 < entry[2] <= 20:
                        tempFn=tempFn+40
                    elif 15 < entry[2] :
                        tempFn=tempFn+100
                    hourly_fitzgerald_number.append(tempFn)
                    
                plog ("Hourly Fitzgerald number")
                plog (hourly_fitzgerald_number)
                plog ("Night's total fitzgerald number")
                plog (sum(hourly_fitzgerald_number))
                
                if sum(hourly_fitzgerald_number) < 10:
                    plog ("This is a good observing night!")
                    self.weather_report_is_acceptable_to_observe=True
                    self.weather_report_wait_until_open=True
                    self.weather_report_wait_until_open_time=ephem_now
                    self.weather_report_close_during_evening=False
                    self.weather_report_close_during_evening_time=ephem_now
                elif sum(hourly_fitzgerald_number) > 1000:
                    plog ("This is a horrible observing night!")
                    self.weather_report_is_acceptable_to_observe=False
                    self.weather_report_wait_until_open=False
                    self.weather_report_wait_until_open_time=ephem_now
                    self.weather_report_close_during_evening=False
                    self.weather_report_close_during_evening_time=ephem_now
                elif sum(hourly_fitzgerald_number) < 100:
                    plog ("This is perhaps not the best night, but we will give it a shot!")
                    self.weather_report_is_acceptable_to_observe=True
                    self.weather_report_wait_until_open=True
                    self.weather_report_wait_until_open_time=ephem_now
                    self.weather_report_close_during_evening=False
                    self.weather_report_close_during_evening_time=ephem_now
                else:
                    plog ("This is a problematic night, lets check if one part of the night is clearer than the other.")
                    TEMPhourly_restofnight_fitzgerald_number=hourly_fitzgerald_number.copy()
                    TEMPhourly_nightuptothen_fitzgerald_number=hourly_fitzgerald_number.copy()
                    hourly_restofnight_fitzgerald_number=[]                
                    
                    for entry in range(len(TEMPhourly_restofnight_fitzgerald_number)):
                        hourly_restofnight_fitzgerald_number.append(sum(TEMPhourly_restofnight_fitzgerald_number))
                        TEMPhourly_restofnight_fitzgerald_number.pop(0)
                    
                    plog ("Hourly Fitzgerald Number for the Rest of the Night")
                    plog (hourly_restofnight_fitzgerald_number)
                    
                    later_clearing_hour=99
                    for q in range(len(hourly_restofnight_fitzgerald_number)):
                        if hourly_restofnight_fitzgerald_number[q] < 100:
                            plog ("looks like it is clear for the rest of the night after hour " + str(q+1) )
                            later_clearing_hour=q+1
                            number_of_hours_left_after_later_clearing_hour= len(hourly_restofnight_fitzgerald_number) - q
                            break                  
                    
                    hourly_nightuptothen_fitzgerald_number=[]
                    counter=0
                    for entry in TEMPhourly_nightuptothen_fitzgerald_number:
                        temp_value=0        
                        for q in range(len(TEMPhourly_nightuptothen_fitzgerald_number)):
                            if q < counter:
                                temp_value = temp_value + TEMPhourly_nightuptothen_fitzgerald_number[q]
                        counter=counter+1
                        
                        hourly_nightuptothen_fitzgerald_number.append(temp_value)
                    
                    plog ("Hourly Fitzgerald Number up until that point in the night")
                    plog (hourly_nightuptothen_fitzgerald_number)
                    
                    clear_until_hour=99
                    for q in range(len(hourly_nightuptothen_fitzgerald_number)):
                        if hourly_nightuptothen_fitzgerald_number[q] < 100:
                            #plog ("looks like it is clear until hour " + str(q+1) )
                            clear_until_hour=q+1            
                                
                    if clear_until_hour != 99:
                        if clear_until_hour > 2:                        
                            plog ("looks like it is clear until hour " + str(clear_until_hour) )
                            plog ("Will observe until then then close down observatory")
                            self.weather_report_is_acceptable_to_observe=True
                            self.weather_report_close_during_evening=True
                            self.weather_report_close_during_evening_time=ephem_now + (clear_until_hour/24)
                            g_dev['events']['Observing Ends'] = ephem_now + (clear_until_hour/24)
                        else:
                            plog ("looks like it is clear until hour " + str(clear_until_hour) )
                            plog ("But that isn't really long enough to rationalise opening the observatory")
                            self.weather_report_is_acceptable_to_observe=False
                            self.weather_report_close_during_evening=False
                    
                    if later_clearing_hour != 99:
                        if number_of_hours_left_after_later_clearing_hour > 2:
                            plog ("looks like clears up at hour " + str(later_clearing_hour) )
                            plog ("Will attempt to open/re-open observatory then.")                    
                            self.weather_report_wait_until_open=True
                            self.weather_report_wait_until_open_time=ephem_now + (later_clearing_hour/24) 
                        else:
                            plog ("looks like it clears up at hour " + str(later_clearing_hour) )
                            plog ("But there isn't much time after then, so not going to open then. ")
                            self.weather_report_wait_until_open=False
                            
                    # if self.weather_report_close_during_evening==True or self.weather_report_wait_until_open==True:
                    #     self.weather_report_is_acceptable_to_observe=True
                    # else:
                    #     self.weather_report_is_acceptable_to_observe=False
                        
                    if clear_until_hour==99 and later_clearing_hour ==99:
                        plog ("It doesn't look like there is a clear enough patch to observe tonight")
                        self.weather_report_is_acceptable_to_observe=False
            except Exception as e:
                plog ("OWN failed", e)
                
                
            
        
        
        
        

        # However, if the observatory is under manual control, leave this switch on.
        enc_status = g_dev['enc'].status
        #try:
        if enc_status is not None:
            if enc_status['mode'] == 'Manual':
                self.weather_report_is_acceptable_to_observe=True
        #except:

            #self.weather_report_is_acceptable_to_observe=True
            
        return
            
    # def global_wx(self):
    #     '''
    #     THIS ROUTINE IS A COMPLETE HACK -- BEWARE.
    #
    #     Next steps: condition night vs day
    #     add aperture size  and solar totalizers
    #     run in reverse for 10-20 years
    #     build a database
    #
    #     '''
    #     # g_dev['ocn'].status = g_dev['ocn'].get_status()
    #     # g_dev['enc'].status = g_dev['enc'].get_status()
    #     # ocn_status = g_dev['ocn'].status
    #     # enc_status = g_dev['enc'].statusl
    #     # events = g_dev['events']
    #     #breakpoint()
    #     obs_win_begin, sunset, sunrise, ephem_now = self.astro_events.getSunEvents()
    #     if True: #self.nightly_weather_report_complete==False:
    #         #self.nightly_weather_report_complete=True
    #         # First thing to do at the Cool Down, Open time is to calculate the quality of the evening
    #         # using the broad weather report.
    #         #             site   >=2m>=1m>m45 sml sol   lat
    #         lat_lons = [['coj ',    1,  2,  2,  3,  1,  -31.272856,  149.070813],
    #                     ['eco ',    0,  0,  1,  1,  0,  -37.700976,  145.191672],
    #                     ['nsq ',    0,  2,  2,  1,  1,   32.354453,  80.0531263],
    #                     ['tlv ',    0,  1,  0,  0,  0,   30.597529,  34.7623430],
    #                     ['cpt ',    0,  2,  1,  1,  1,  -32.380561,  20.810137 ],
    #                     ['tfn ',    0,  2,  1,  1,  1,   28.302079, -16.5113277],
    #                     ['lsc ',    0,  3,  2,  1,  1,  -30.167654, -70.804709 ],
    #                     ['roc ',    0,  0,  2,  0,  0,   42.250616, -77.7850655],
    #                     ['elp ',    0,  2,  1,  1,  0,   30.679280, -104.024396],
    #                     ['aro ',    0,  0,  3,  1,  1,   35.554307, -105.870189],
    #                     ['udro',    0,  0,  1,  1,  0,   37.737001, -113.691774],
    #                     ['sro ',    0,  0,  1,  1,  0,   37.070365, -119.413107],
    #                     ['mrc ',    0,  0,  2,  2,  1,   34.459375, -119.681172],
    #                     ['sqa ',    0,  0,  1,  0,  0,   34.691481, -120.042251],
    #                     ['ogg ',    1,  0,  4,  2,  1,   20.707034, -156.257481],
    #                     ['whs ',    0,  0,  1,  0,  0,   21.388383, -157.993459]]
    #         plog("Appraising quality of evening from Open Weather Map.")
    #         owm = OWM('d5c3eae1b48bf7df3f240b8474af3ed0')
    #         mgr = owm.weather_manager()
    #         total_clear_hrs = 0
    #         total_cloudy_hrs = 0
    #         for site in lat_lons:
    #             one_call = mgr.one_call(lat=site[-2], lon=site[-1])
    #             breakpoint()
    #             two_day = one_call.forecast_hourly
    #             clear_hrs = 0
    #             cloudy_hrs = 0
    #
    #             #print( '\n' + site[0], two_day, '\n' + site[0], '\n\n')
    #             for hourly_report in two_day:
    #                 if hourly_report.status in ['Clear']:
    #                     clear_hrs += 1
    #                     total_clear_hrs += 1
    #                     #print("Bingo")
    #                 else:
    #                     cloudy_hrs += 1
    #                     total_cloudy_hrs += 1
    #             print('Clear  Fraction:  ' + site[0], round(clear_hrs*100/(clear_hrs + cloudy_hrs), 1), '\t', clear_hrs/2)
    #            # breakpoint()
    #         print('Global Fraction:      ', round(total_clear_hrs*100/(total_clear_hrs + total_cloudy_hrs), 1), '\t', total_clear_hrs/2)
    #         breakpoint()
    #         """
    #         https://api.openweathermap.org/data/3.0/onecall/timemachine?lat=34.459375&lon=-119.681172&dt=1580052892&appid=d5c3eae1b48bf7df3f240b8474af3ed0
    #         The above return historical values for the nominated timestamp.
    #         """
    #         # # Collect relevant info for fitzgerald weather number calculation
    #         hourcounter=0
    #         # fitzgerald_weather_number_grid=[]
    #         # hours_until_end_of_observing= math.ceil((events['Observing Ends'] - ephem_now) * 24)
    #         # plog("Hours until end of observing: " + str(hours_until_end_of_observing))
    #
    #
    #         # for hourly_report in one_call.forecast_hourly:
    #
    #         #     if hourcounter > hours_until_end_of_observing:
    #         #         pass
    #         #     else:
    #         #         fitzgerald_weather_number_grid.append([hourly_report.humidity,hourly_report.clouds,hourly_report.wind()['speed'],hourly_report.status, hourly_report.detailed_status])
    #         #         hourcounter=hourcounter + 1
    #         # plog (fitzgerald_weather_number_grid)
    #
    #
    #         # Fitzgerald weather number calculation.
    #         hourly_fitzgerald_number=[]
    #         fitzgerald_weather_number_grid = 0  #Hack!!
    #         for entry in fitzgerald_weather_number_grid:
    #             tempFn=0
    #             # Add humidity score up
    #             if 80 < entry[0] <= 85:
    #                 tempFn=tempFn+1
    #             elif 85 < entry[0] <= 90:
    #                 tempFn=tempFn+4
    #             elif 90 < entry[0] <= 100:
    #                 tempFn=tempFn+40
    #
    #             # Add cloud score up
    #             if 20 < entry[1] <= 40:
    #                 tempFn=tempFn+1
    #             elif 40 < entry[1] <= 60:
    #                 tempFn=tempFn+4
    #             elif 60 < entry[1] <= 80:
    #                 tempFn=tempFn+40
    #             elif 80 < entry[1] <= 100:
    #                 tempFn=tempFn+100
    #
    #             # Add wind score up
    #             if 8 < entry[2] <=12:
    #                 tempFn=tempFn+1
    #             elif 12 < entry[2] <= 15:
    #                 tempFn=tempFn+4
    #             elif 15 < entry[2] <= 20:
    #                 tempFn=tempFn+40
    #             elif 15 < entry[2] :
    #                 tempFn=tempFn+100
    #             hourly_fitzgerald_number.append(tempFn)
    #
    #         plog ("Hourly Fitzgerald number")
    #         plog (hourly_fitzgerald_number)
    #         plog ("Night's total fitzgerald number")
    #         plog (sum(hourly_fitzgerald_number))
    #
    #         if sum(hourly_fitzgerald_number) < 10:
    #             plog ("This is a good observing night!")
    #             self.weather_report_is_acceptable_to_observe=True
    #             self.weather_report_wait_until_open=True
    #             self.weather_report_wait_until_open_time=ephem_now
    #             self.weather_report_close_during_evening=False
    #             self.weather_report_close_during_evening_time=ephem_now
    #         elif sum(hourly_fitzgerald_number) > 1000:
    #             plog ("This is a horrible observing night!")
    #             self.weather_report_is_acceptable_to_observe=False
    #             self.weather_report_wait_until_open=False
    #             self.weather_report_wait_until_open_time=ephem_now
    #             self.weather_report_close_during_evening=False
    #             self.weather_report_close_during_evening_time=ephem_now
    #         elif sum(hourly_fitzgerald_number) < 100:
    #             plog ("This is perhaps not the best night, but we will give it a shot!")
    #             self.weather_report_is_acceptable_to_observe=True
    #             self.weather_report_wait_until_open=True
    #             self.weather_report_wait_until_open_time=ephem_now
    #             self.weather_report_close_during_evening=False
    #             self.weather_report_close_during_evening_time=ephem_now
    #         else:
    #             plog ("This is a problematic night, lets check if one part of the night is clearer than the other.")
    #             TEMPhourly_restofnight_fitzgerald_number=hourly_fitzgerald_number.copy()
    #             TEMPhourly_nightuptothen_fitzgerald_number=hourly_fitzgerald_number.copy()
    #             hourly_restofnight_fitzgerald_number=[]
    #
    #             for entry in range(len(TEMPhourly_restofnight_fitzgerald_number)):
    #                 hourly_restofnight_fitzgerald_number.append(sum(TEMPhourly_restofnight_fitzgerald_number))
    #                 TEMPhourly_restofnight_fitzgerald_number.pop(0)
    #
    #             plog ("Hourly Fitzgerald Number for the Rest of the Night")
    #             plog (hourly_restofnight_fitzgerald_number)
    #
    #             later_clearing_hour=99
    #             for q in range(len(hourly_restofnight_fitzgerald_number)):
    #                 if hourly_restofnight_fitzgerald_number[q] < 100:
    #                     plog ("looks like it is clear for the rest of the night after hour " + str(q+1) )
    #                     later_clearing_hour=q+1
    #                     number_of_hours_left_after_later_clearing_hour= len(hourly_restofnight_fitzgerald_number) - q
    #                     break
    #
    #             hourly_nightuptothen_fitzgerald_number=[]
    #             counter=0
    #             for entry in TEMPhourly_nightuptothen_fitzgerald_number:
    #                 temp_value=0
    #                 for q in range(len(TEMPhourly_nightuptothen_fitzgerald_number)):
    #                     if q < counter:
    #                         temp_value = temp_value + TEMPhourly_nightuptothen_fitzgerald_number[q]
    #                 counter=counter+1
    #
    #                 hourly_nightuptothen_fitzgerald_number.append(temp_value)
    #
    #             plog ("Hourly Fitzgerald Number up until that point in the night")
    #             plog (hourly_nightuptothen_fitzgerald_number)
    #
    #             clear_until_hour=99
    #             for q in range(len(hourly_nightuptothen_fitzgerald_number)):
    #                 if hourly_nightuptothen_fitzgerald_number[q] < 100:
    #                     #plog ("looks like it is clear until hour " + str(q+1) )
    #                     clear_until_hour=q+1
    #
    #             if clear_until_hour != 99:
    #                 if clear_until_hour > 2:
    #                     plog ("looks like it is clear until hour " + str(clear_until_hour) )
    #                     plog ("Will observe until then then close down observatory")
    #                     self.weather_report_is_acceptable_to_observe=True
    #                     self.weather_report_close_during_evening=True
    #                     self.weather_report_close_during_evening_time=ephem_now + (clear_until_hour/24)
    #                     g_dev['events']['Observing Ends'] = ephem_now + (clear_until_hour/24)
    #                 else:
    #                     plog ("looks like it is clear until hour " + str(clear_until_hour) )
    #                     plog ("But that isn't really long enough to rationalise opening the observatory")
    #                     self.weather_report_is_acceptable_to_observe=False
    #                     self.weather_report_close_during_evening=False
    #
    #             if later_clearing_hour != 99:
    #                 if number_of_hours_left_after_later_clearing_hour > 2:
    #                     plog ("looks like clears up at hour " + str(later_clearing_hour) )
    #                     plog ("Will attempt to open/re-open observatory then.")
    #                     self.weather_report_wait_until_open=True
    #                     self.weather_report_wait_until_open_time=ephem_now + (later_clearing_hour/24)
    #                 else:
    #                     plog ("looks like it clears up at hour " + str(later_clearing_hour) )
    #                     plog ("But there isn't much time after then, so not going to open then. ")
    #                     self.weather_report_wait_until_open=False
    #
    #             # if self.weather_report_close_during_evening==True or self.weather_report_wait_until_open==True:
    #             #     self.weather_report_is_acceptable_to_observe=True
    #             # else:
    #             #     self.weather_report_is_acceptable_to_observe=False
    #
    #             if clear_until_hour==99 and later_clearing_hour ==99:
    #                 plog ("It doesn't look like there is a clear enough patch to observe tonight")
    #                 self.weather_report_is_acceptable_to_observe=False
    #     return
                    
                
            
        
        
        
        
        
if __name__ == "__main__":
    wema = WxEncAgent(ptr_config.wema_name, ptr_config.wema_config)
    wema.run()
