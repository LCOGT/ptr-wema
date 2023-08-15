"""
WER 20210624

First attempt at having a parallel dedicated agent for weather and enclosure.
This code should be as simple and reliable as possible, no hanging variables,
etc.

This would be a good place to log the weather data and any enclosure history,
once this code is stable enough to run as a service.

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
#import redis
#import datetime
import traceback
import ephem
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

from wema_config import get_enc_status_custom
from wema_config import get_ocn_status_custom

# FIXME: This needs attention once we figure out the restart_obs script.
def terminate_restart_observer(site_path, no_restart=False):
    """Terminates obs-platform code if running and restarts obs."""
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
    payload = {"statusType": str(column), "status": status_to_send}\

    data = json.dumps(payload)
    try:
        response = requests.post(uri_status, data=data, timeout=20)

        if response.ok:
           # pass
           print("~")
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
        g_dev["wema"] = self
        #g_dev['debug'] = False
       
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
        #if self.hostname in self.config["wema_hostname"]:
        #    self.is_wema = True
        #    self.is_process = False

        #self.site = config["site"]
        self.debug_flag = self.config['debug_mode']
        self.admin_only_flag = self.config['admin_owner_commands_only']
        if self.debug_flag:
            self.debug_lapse_time = time.time() + self.config['debug_duration_sec']
            g_dev['debug'] = True
            #g_dev['obs'].open_and_enabled_to_observe = True
        else:
            self.debug_lapse_time = 0.0
            g_dev['debug'] = False
            #g_dev['obs'].open_and_enabled_to_observe = False

        if True:  #self.config["wema_is_active"]:
            self.hostname = self.hostname = socket.gethostname()
            if self.hostname in self.config["wema_hostname"]:
                self.is_wema = True
                g_dev["wema_write_share_path"] = config["wema_path"]
                self.wema_path = g_dev["wema_write_share_path"]
                self.site_path = self.wema_path
            else:
                # This host is a client
                self.is_wema = False  # This is a client.
                self.site_path = config["wema_path"]
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

        obs_win_begin, sunZ88Op, sunZ88Cl, ephem_now = self.astro_events.getSunEvents()
        self.weather_report_open_during_evening = False
        self.weather_report_open_during_evening_time = ephem_now
        self.weather_report_close_during_evening = False
        self.weather_report_close_during_evening_time = ephem_now + 86400
        self.nightly_weather_report_complete = False

        self.weather_report_run_timer=time.time()-3600
        


        self.open_and_enabled_to_observe = False

        #self.local_weather_always_overrides_OWM=config['local_weather_always_overrides_OWM']

        self.owm_active=config['OWM_active']
        self.local_weather_active=config['local_weather_active']
        
        self.enclosure_status_check_period=config['enclosure_status_check_period']
        self.weather_status_check_period = config['weather_status_check_period']
        self.safety_status_check_period = config['safety_status_check_period']
        self.scan_requests_check_period = 4
        self.wema_settings_upload_period = 10

        # Timers rather than time.sleeps
        self.enclosure_status_check_timer=time.time() - 2*self.enclosure_status_check_period
        self.weather_status_check_timer = time.time() - 2*self.weather_status_check_period
        self.safety_check_timer=time.time() - 2*self.safety_status_check_period
        self.scan_requests_timer=time.time() -2 * self.scan_requests_check_period
        self.wema_settings_upload_timer=time.time() -2 * self.wema_settings_upload_period


        self.rain_limit_quiet=False
        self.cloud_limit_quiet=False
        self.humidity_limit_quiet=False
        self.windspeed_limit_quiet=False
        self.lightning_limit_quiet=False
        self.temp_minus_dew_quiet=False
        self.skytemp_limit_quiet=False
        self.hightemp_limit_quiet=False
        self.lowtemp_limit_quiet=False

        if self.config['observing_conditions']['observing_conditions1']['driver'] == None:
            self.ocn_exists=False
        else:
            self.ocn_exists=True

        # This variable prevents the roof being called to open every loop...        
        self.enclosure_next_open_time = time.time()
        # This keeps a track of how many times the roof has been open this evening
        # Which is really a measure of how many times the enclosure has
        # attempted to observe but been shut on....
        # If it is too many, then it shuts down for the whole evening. 
        self.opens_this_evening = 0
        self.local_weather_ok = None

        # The weather report has to be at least passable at some time of the night in order to 
        # allow the enclosure to become active and observe. This doesn't mean that it is
        # necessarily a GOOD night at all, just that there are patches of feasible
        # observing during the night.
        #self.nightly_weather_report_complete = False
        self.weather_report_is_acceptable_to_observe = False
        # If the night is patchy, the weather report can identify a later time to open
        # or to close the enclosure early during the night.
        obs_win_begin, sunZ88Op, sunZ88Cl, ephem_now = self.astro_events.getSunEvents()
        self.weather_report_open_during_evening=False
        self.weather_report_open_during_evening_time=ephem_now
        self.weather_report_close_during_evening=False
        self.weather_report_close_during_evening_time=ephem_now
        self.hourly_report_holder=[]
        self.weather_report_open_at_start = False
        self.nightly_reset_complete = False
      
        self.keep_open_all_night = False
        self.keep_closed_all_night   = False          
        self.open_at_specific_utc = False
        self.specific_utc_when_to_open = -1.0  
        self.manual_weather_hold_set = False
        self.manual_weather_hold_duration = -1.0
    
        self.wema_has_roof_control=config['wema_has_control_of_roof']



        # This prevents commands from previous nights/runs suddenly running
        # when wema.py is booted (has happened a bit!)
        url_job = "https://jobs.photonranch.org/jobs/getnewjobs"
        body = {"site": self.config['wema_name']}
        #cmd = {}
        # Get a list of new jobs to complete (this request
        # marks the commands as "RECEIVED")
        requests.request(
            "POST", url_job, data=json.dumps(body), timeout=30
        ).json()


        #self.update_status()
        #breakpoint()
        # Run a weather report on bootup so enclosure can run if need be.
        if not g_dev['debug']:
            # self.global_wx()
            if self.enc_status_custom:
                enc_status={}
                enc_status['enclosure']={}

                enc_status['enclosure']['enclosure1']= get_enc_status_custom()
                self.run_nightly_weather_report(enc_status=enc_status)
            else:
                self.run_nightly_weather_report(enc_status=g_dev['enc'].get_status())
        else:
            if self.enc_status_custom:
                enc_status={}
                enc_status['enclosure']={}

                enc_status['enclosure']['enclosure1']= get_enc_status_custom()
                self.run_nightly_weather_report(enc_status=enc_status)
            else:
                self.run_nightly_weather_report(enc_status=g_dev['enc'].get_status())
            self.weather_report_is_acceptable_to_observe = True
            self.weather_report_open_during_evening = False


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
 
                if dev_type == "observing_conditions" and not self.config['observing_conditions']['observing_conditions1']['ocn_is_custom']:

                    device = ObservingConditions(
                        driver, name, self.config, self.astro_events
                    )
                    self.ocn_status_custom=False
                elif dev_type == "observing_conditions" and self.config['observing_conditions']['observing_conditions1']['ocn_is_custom']:
                    #plog("breakpoint")
                    
                    device=None
                    self.ocn_status_custom=True
                    #get_ocn_status()
                    #breakpoint()
                    
                elif dev_type == "enclosure" and not self.config['enclosure']['enclosure1']['enc_is_custom']:
                    device = Enclosure(driver, name, self.config, self.astro_events)
                    self.enc_status_custom=False
                elif dev_type == "enclosure" and self.config['enclosure']['enclosure1']['enc_is_custom']:
                    
                    device=None
                    self.enc_status_custom=True
                    #get_enc_status()
                    #breakpoint()
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

    def scan_requests(self):
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


        url_job = "https://jobs.photonranch.org/jobs/getnewjobs"
        body = {"site": self.config['wema_name']}
        cmd = {}
        # Get a list of new jobs to complete (this request
        # marks the commands as "RECEIVED")
        #plog ("scanning requests")
        try:
            unread_commands = requests.request(
                "POST", url_job, data=json.dumps(body), timeout=20
            ).json()
        except:
            plog(traceback.format_exc())
            plog("problem gathering scan requests. Likely just a connection glitch.")
            #breakpoint()
            unread_commands = []
        # Make sure the list is sorted in the order the jobs were issued
        # Note: the ulid for a job is a unique lexicographically-sortable id.
        if len(unread_commands) > 0:
            try:
                unread_commands.sort(key=lambda x: x["timestamp_ms"])
                # Process each job one at a time
                for cmd in unread_commands:


                    plog(cmd)

            except:
                if 'Internal server error' in str(unread_commands):
                    plog("AWS server glitch reading unread_commands")
                else:
                    plog(traceback.format_exc())
                    plog("unread commands")
                    plog(unread_commands)
                    plog("MF trying to find whats happening with this relatively rare bug!")

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
        
        enc_status = None
        ocn_status = None
        #device_status = None
        obsy = self.config['wema_name']   #  This is meant to be for the wema, not an OBSP.


        # Hourly Weather Report
        if time.time() > (self.weather_report_run_timer + 3600):
            self.weather_report_run_timer=time.time()
            if self.enc_status_custom:
                enc_status={}
                enc_status['enclosure']={}

                enc_status['enclosure']['enclosure1']= get_enc_status_custom()
                self.run_nightly_weather_report(enc_status=enc_status)
            else:
                self.run_nightly_weather_report(enc_status=g_dev['enc'].get_status())
        
        
            
            


        # Enclosure Status
        if time.time() > self.enclosure_status_check_timer + self.enclosure_status_check_period:
            self.enclosure_status_check_timer = time.time()
            status = {}
            status["timestamp"] = round(time.time(), 1)
            status['enclosure']={}
            if self.enc_status_custom==False:
                device=self.all_devices.get('enclosure', {})['enclosure1']
                status['enclosure']['enclosure1'] = device.get_status()
                enc_status = {"enclosure": status.pop("enclosure")}
            else:
                enc_status={}
                enc_status['enclosure']={}

                enc_status['enclosure']['enclosure1']= get_enc_status_custom()

            if enc_status is not None:
                # New Tim Entries
                if enc_status['enclosure']['enclosure1']['shutter_status'] == 'Open':
                    enc_status['enclosure']['enclosure1']['enclosure_is_open'] = True
                    enc_status['enclosure']['enclosure1']['shut_reason_bad_weather'] = False
                    enc_status['enclosure']['enclosure1']['shut_reason_daytime'] = False
                    enc_status['enclosure']['enclosure1']['shut_reason_manual_mode'] = False
                else:
                    enc_status['enclosure']['enclosure1']['enclosure_is_open'] = False
                    if not enc_status['enclosure']['enclosure1']['enclosure_mode'] == 'Automatic':
                        enc_status['enclosure']['enclosure1']['shut_reason_manual_mode'] = True
                    else:
                        enc_status['enclosure']['enclosure1']['shut_reason_manual_mode'] = False
                    if ocn_status is not None:  #NB NB ocn status has never been established first time this is envoked after startup -WER
                        if ocn_status['observing_conditions']['observing_conditions1']['wx_ok'] == 'Unknown':
                            enc_status['enclosure']['enclosure1']['shut_reason_bad_weather'] = False
                        elif ocn_status['observing_conditions']['observing_conditions1']['wx_ok'] == 'No' or not self.weather_report_is_acceptable_to_observe:
                            enc_status['enclosure']['enclosure1']['shut_reason_bad_weather'] = True
                    elif not self.weather_report_is_acceptable_to_observe:
                        enc_status['enclosure']['enclosure1']['shut_reason_bad_weather'] = True
                    else:
                        enc_status['enclosure']['enclosure1']['shut_reason_bad_weather'] = False

                        # NEED TO INCLUDE WEATHER REPORT AND FITZ NUMBER HERE

                    if g_dev['events']['Cool Down, Open'] < ephem.now() or ephem.now() < g_dev['events'][
                        'Close and Park'] > ephem.now():
                        enc_status['enclosure']['enclosure1']['shut_reason_daytime'] = True
                    else:
                        enc_status['enclosure']['enclosure1']['shut_reason_daytime'] = False

                if enc_status is not None:
                    lane = "enclosure"
                    try:                        
                        send_status(obsy, lane, enc_status)
                    except:
                        plog('could not send enclosure status')


        if time.time() > self.weather_status_check_timer + self.weather_status_check_period:
            self.weather_status_check_timer=time.time()
            status = {}
            status["timestamp"] = round(time.time(), 1)
            status['observing_conditions'] = {}
            if self.ocn_status_custom==False:
                device = self.all_devices.get('observing_conditions', {})['observing_conditions1']
                
                #breakpoint()
                
                if device == None:
                    status['observing_conditions']['observing_conditions1'] = None
                else:
                    status['observing_conditions']['observing_conditions1'] = device.get_status()
                    ocn_status = {"observing_conditions": status.pop("observing_conditions")}
            else:
                ocn_status={}
                ocn_status['observing_conditions']={}
                ocn_status['observing_conditions']['observing_conditions1'] = get_ocn_status_custom()

            if ocn_status is None or ocn_status['observing_conditions']['observing_conditions1']  == None:   #20230709 Changed from not None
                ocn_status = {}
                ocn_status['observing_conditions'] = {}
                #if ocn_status['observing_conditions']['observing_conditions1'] == None:
                ocn_status['observing_conditions']['observing_conditions1'] = dict(wx_ok='Unknown',
                                                                                       wx_hold='no',
                                                                                       hold_duration=0)


            ocn_status['observing_conditions']['observing_conditions1']['weather_report_good'] = self.weather_report_is_acceptable_to_observe
            try:
                ocn_status['observing_conditions']['observing_conditions1']['fitzgerald_number'] = self.night_fitzgerald_number
            except:
                pass


            #breakpoint()
            if self.enclosure_next_open_time - time.time() > 0:
                ocn_status['observing_conditions']['observing_conditions1']['hold_duration'] = self.enclosure_next_open_time - time.time()
            else:
                ocn_status['observing_conditions']['observing_conditions1']['hold_duration'] = 0
            
            
            ocn_status['observing_conditions']['observing_conditions1']["wx_hold"] = not self.local_weather_ok
    
            if ocn_status is not None:
                lane = "weather"
                try:
                    # time.sleep(2)
                    send_status(obsy, lane, ocn_status)
                except:
                    plog('could not send weather status')                  

            loud = False
            if loud:
                print("\n\n > Status Sent:  \n", ocn_status)

        # WEMA Settings
        if time.time() > self.wema_settings_upload_timer + self.wema_settings_upload_period:
            self.wema_settings_upload_timer = time.time()
            plog("wema settings upload")
            status = {}
            status["timestamp"] = round(time.time(), 1)
            status['wema_settings']={}
            
            
            status['wema_settings']['OWM_active']=self.owm_active
            status['wema_settings']['local_weather_active']=self.local_weather_active
            status['wema_settings']['keep_roof_open_all_night'] = self.keep_open_all_night
            status['wema_settings']['keep_roof_closed_all_night']  = self.keep_closed_all_night
            
            status['wema_settings']['open_at_specific_utc'] = self.open_at_specific_utc
            status['wema_settings']['specific_utc_when_to_open'] = self.specific_utc_when_to_open
            
            status['wema_settings']['manual_weather_hold_set'] = self.manual_weather_hold_set
            status['wema_settings']['manual_weather_hold_duration'] = self.manual_weather_hold_duration
            
                    
            if self.ocn_exists:
                # Local Weather Limits
                status['wema_settings']['rain_limit_on'] = g_dev['ocn'].rain_limit_on
                status['wema_settings']['rain_limit_quiet'] = self.rain_limit_quiet
                status['wema_settings']['rain_limit_warning_level'] = g_dev['ocn'].warning_rain_limit_setting
                status['wema_settings']['rain_limit_danger_level'] = g_dev['ocn'].rain_limit_setting
                
                status['wema_settings']['cloud_limit_on'] = g_dev['ocn'].cloud_cover_limit_on
                status['wema_settings']['cloud_limit_quiet'] = self.cloud_limit_quiet
                status['wema_settings']['cloud_limit_warning_level'] = g_dev['ocn'].warning_cloud_cover_limit_setting
                status['wema_settings']['cloud_limit_danger_level'] = g_dev['ocn'].cloud_cover_limit_setting
                
                status['wema_settings']['humidity_limit_on']  = g_dev['ocn'].humidity_limit_on
                status['wema_settings']['humidity_limit_quiet'] = self.humidity_limit_quiet
                status['wema_settings']['humidity_limit_warning_level'] = g_dev['ocn'].warning_humidity_limit_setting
                status['wema_settings']['humidity_limit_danger_level'] = g_dev['ocn'].humidity_limit_setting
                
                status['wema_settings']['windspeed_limit_on']  = g_dev['ocn'].windspeed_limit_on
                status['wema_settings']['windspeed_limit_quiet'] = self.windspeed_limit_quiet
                status['wema_settings']['windspeed_limit_warning_level'] = g_dev['ocn'].warning_windspeed_limit_setting
                status['wema_settings']['windspeed_limit_danger_level'] = g_dev['ocn'].windspeed_limit_setting
                
                status['wema_settings']['lightning_limit_on']  = g_dev['ocn'].lightning_limit_on
                status['wema_settings']['lightning_limit_quiet'] = self.lightning_limit_quiet
                status['wema_settings']['lightning_limit_warning_level'] = g_dev['ocn'].warning_lightning_limit_setting
                status['wema_settings']['lightning_limit_danger_level'] =  g_dev['ocn'].lightning_limit_setting
                
                status['wema_settings']['tempminusdew_limit_on']  = g_dev['ocn'].temp_minus_dew_on
                status['wema_settings']['tempminusdew_limit_quiet'] = self.temp_minus_dew_quiet
                status['wema_settings']['tempminusdew_limit_warning_level'] = g_dev['ocn'].warning_temp_minus_dew_setting
                status['wema_settings']['tempminusdew_limit_danger_level'] = g_dev['ocn'].temp_minus_dew_setting
                
                status['wema_settings']['skytemp_limit_on']  = g_dev['ocn'].sky_temperature_limit_on
                status['wema_settings']['skytemp_limit_quiet'] = self.skytemp_limit_quiet
                status['wema_settings']['skytemp_limit_warning_level'] = g_dev['ocn'].warning_sky_temp_limit_setting
                status['wema_settings']['skytemp_limit_danger_level'] = g_dev['ocn'].sky_temp_limit_setting
                
                status['wema_settings']['hightemperature_limit_on']  = g_dev['ocn'].highest_temperature_on
                status['wema_settings']['hightemperature_limit_quiet'] = self.hightemp_limit_quiet
                status['wema_settings']['hightemperature_limit_warning_level'] = g_dev['ocn'].warning_highest_temperature_setting
                status['wema_settings']['hightemperature_limit_danger_level'] = g_dev['ocn'].highest_temperature_setting
                
                status['wema_settings']['lowtemperature_limit_on']  = g_dev['ocn'].lowest_temperature_on
                status['wema_settings']['lowtemperature_limit_quiet'] = self.lowtemp_limit_quiet
                status['wema_settings']['lowtemperature_limit_warning_level'] = g_dev['ocn'].warning_lowest_temperature_setting
                status['wema_settings']['lowtemperature_limit_danger_level'] = g_dev['ocn'].lowest_temperature_setting
                
            lane = "wema_settings"
            try:
                # time.sleep(2)
                send_status(obsy, lane, status)
            except:
                plog('could not send wema_settings status') 
            
            
            #plog(status)

    def update(self):     ## NB NB NB This is essentially the sequencer for the WEMA.
        self.update_status()

        if time.time() > self.scan_requests_timer + self.scan_requests_check_period:
            self.scan_requests_timer=time.time()
            self.scan_requests()


        if time.time() > self.safety_check_timer + self.safety_status_check_period:
            self.safety_check_timer=time.time()

            # Here it runs through the various checks and decides whether to open or close the roof or not.
            # Check for delayed opening of the enclosure and act accordingly.
            
            

            # If the enclosure is simply delayed until opening, then wait until then, then attempt to start up the enclosure
            obs_win_begin, sunZ88Op, sunZ88Cl, ephem_now = self.astro_events.getSunEvents()
            if (g_dev['events']['Cool Down, Open'] <= ephem_now):
                self.nightly_reset_complete = False

            if (g_dev['events']['Close and Park'] <= ephem_now):
                self.nightly_reset_complete = False
            if self.ocn_status_custom==False:                            
                ocn_status = g_dev['ocn'].get_status()
            else:
                ocn_status = get_ocn_status_custom()
            if self.enc_status_custom==False:                
                enc_status = g_dev['enc'].get_status()
            else:
                enc_status = get_enc_status_custom()
            #breakpoint()

            if ocn_status==None:
                self.local_weather_ok = None
            else:
                if 'wx_ok' in ocn_status:
                    if ocn_status['wx_ok'] == 'Yes':
                        self.local_weather_ok = True
                    elif ocn_status['wx_ok'] == 'No':
                        self.local_weather_ok = False
                    else:
                        self.local_weather_ok = None
                else:
                    self.local_weather_ok = None

            plog("***************************************************************")
            plog("Current time             : " + str(time.asctime()))
            plog("Shutter Status           : " + str(enc_status['shutter_status']))
            if ocn_status == None:
                plog("This WEMA does not report observing conditions")
            else:
                plog("Observing Conditions      : " +str(ocn_status))
                
            if self.local_weather_ok == None:
                plog("No information on local weather available.")
            else:
                plog("Local Weather Ok to Observe  : " +str(self.local_weather_ok))
                if not self.local_weather_active:
                    plog ("However, Local Weather control is set off")
            
            if enc_status['enclosure_mode'] == 'Manual':
                plog ("Weather Considerations overriden due to being in Manual or debug mode: ")
            
            plog("Weather Report Good to Observe: " + str(self.weather_report_is_acceptable_to_observe))
            plog("Time until Cool and Open      : " + str(round(( g_dev['events']['Cool Down, Open'] - ephem_now) * 24,2)) + " hours")
            plog("Time until Close and Park     : "+ str(round(( g_dev['events']['Close and Park'] - ephem_now) * 24,2)) + " hours")
            plog("Time until Nightly Reset      : " + str(round((g_dev['events']['Nightly Reset'] - ephem_now) * 24, 2)) + " hours")
            plog("Nightly Reset Complete        : " + str(self.nightly_reset_complete))
            plog("\n")



            if len(self.hourly_report_holder) > 0:
                pasttitle=False
                for line in self.hourly_report_holder:
                    plog(str(line))

                    if pasttitle==True:
                        current_utc_hour= float(line.split(' ')[0])
                        if self.weather_report_open_during_evening:
                            #breakpoint()
                            if current_utc_hour <= (ephem.Date(self.weather_report_open_during_evening_time).datetime().hour) < (current_utc_hour + 1):
                                plog ("OWM would plan to open the roof")
                        if self.weather_report_close_during_evening:
                            if current_utc_hour <= (ephem.Date(self.weather_report_close_during_evening_time).datetime().hour) < (
                                    current_utc_hour + 1):
                                plog("OWM would plan to close the roof")
                                

                    if 'Hour(UTC)' in line:
                        pasttitle=True
                        plog("-----------------------------")
                        if g_dev['events']['Cool Down, Open'] > ephem_now:
                            plog("Cool Down Open")
                        if self.weather_report_open_at_start:
                            plog("OWM would plan to open at this point.")
                        else:
                            plog("OWM would keep the roof shut at this point.")
                if g_dev['events']['Close and Park'] > ephem_now:
                    plog("Close and Park")
                plog("-----------------------------")
            #breakpoint()
            # if self.weather_report_open_at_start:
            #     plog ("OWM reports that it thinks it should open at the beginning of the calendar.")

            # if self.weather_report_open_during_evening and self.weather_report_close_during_evening:
            #     if self.weather_report_close_during_evening_time > self.weather_report_open_during_evening_time:
            #         plog("OWM reports that it thinks it should open later on in " + str(round(float(self.weather_report_open_during_evening_time - ephem_now) * 24,2))+ " hours.")
            #         plog("OWN reports that it thinks it should close later on in " + str(round(float(self.weather_report_close_during_evening_time - ephem_now) * 24,2)) + " hours.")
            #     else:
            #         plog("OWN reports that it thinks it should close later on in " + str(round(float(self.weather_report_close_during_evening_time - ephem_now) * 24,2)) + " hours.")
            #         plog("OWM reports that it thinks it should open later on in " + str(
            #             round(float(self.weather_report_open_during_evening_time - ephem_now) * 24, 2)) + " hours.")
            #         #breakpoint()


            # elif self.weather_report_open_during_evening:
            #     plog("OWM reports that it thinks it should open later on in " + str(
            #         round(float(self.weather_report_open_during_evening_time - ephem_now) * 24, 2)) + " hours.")


            # elif self.weather_report_close_during_evening:
            #     plog("OWN reports that it thinks it should close later on in " + str(round(float(self.weather_report_close_during_evening_time - ephem_now) * 24,2)) + " hours.")

            if (self.weather_report_close_during_evening or self.weather_report_open_during_evening) and not self.owm_active:
                plog ("OWM information is advisory only, it is currently inactive.")
            
            
            
            
            if (self.weather_report_close_during_evening or self.weather_report_open_during_evening) and self.owm_active:
                plog ("OWM predicts it will set to open/close the roof at these times .")
            
            plog("**************************************************************")

            if (g_dev['events']['Nightly Reset'] <= ephem.now() < g_dev['events']['End Nightly Reset']): # and g_dev['enc'].mode == 'Automatic' ):
                if self.nightly_reset_complete == False:
                    self.nightly_reset_complete = True
                    self.nightly_reset_script(enc_status)


            #try:
            #    multiplier = min(len(wx_reasons),3)
            #except:
            #    multiplier = 1
            #wx_delay_time *= multiplier/2   #Stretch out the Wx hold if there are multiple reasons

            # Safety checks here
            if not g_dev['debug'] and self.open_and_enabled_to_observe and g_dev['enc'].mode == 'Automatic':
                if enc_status is not None:
                    if enc_status['shutter_status'] == 'Software Fault':
                        plog("Software Fault Detected. Will alert the authorities!")
                        self.open_and_enabled_to_observe = False
                        self.park_enclosure_and_close()
                        
                    if enc_status['shutter_status'] == 'Closing':
                        # if self.config['obsid_roof_control'] and g_dev['enc'].mode == 'Automatic':
                        plog("Detected Roof Closing.")
                        self.open_and_enabled_to_observe = False
                        self.enclosure_next_open_time = time.time(
                         ) + self.config['roof_open_safety_base_time'] * self.opens_this_evening

                    if enc_status['shutter_status'] == 'Error':
                        if  enc_status['enclosure_mode'] == 'Automatic':
                            plog("Detected an Error in the Roof Status. Packing up for safety.")
                            self.open_and_enabled_to_observe = False
                            self.park_enclosure_and_close()
                            self.enclosure_next_open_time = time.time(
                            ) + self.config['roof_open_safety_base_time'] * self.opens_this_evening
                            
                else:
                    plog("Enclosure roof status probably not reporting correctly. WEMA down?")

            roof_should_be_shut = False

            if not (g_dev['events']['Cool Down, Open'] < ephem_now < g_dev['events']['Close and Park']):
                roof_should_be_shut = True
                self.open_and_enabled_to_observe = False

            if enc_status['shutter_status'] == 'Open':
                if roof_should_be_shut == True and enc_status['enclosure_mode'] == 'Automatic':
                    plog("Safety check notices that the roof was open outside of the normal observing period")
                    self.park_enclosure_and_close()
                
                if not (self.local_weather_ok == None) and enc_status['enclosure_mode'] == 'Automatic':
                    if (not self.local_weather_ok and self.local_weather_active):
                        plog("Safety check notices that the local weather is not ok. Shutting the roof.")
                        self.park_enclosure_and_close()
                

            if (self.enclosure_next_open_time - time.time()) > 0:
                plog("opens this eve: " + str(self.opens_this_evening))

                plog("minutes until next open attempt ALLOWED: " +
                     str((self.enclosure_next_open_time - time.time()) / 60))

            # # If OWM wants to open the roof later, this is where it checks if it is past that time. 
            # if self.weather_report_open_during_evening and not self.cool_down_latch and enc_status['enclosure_mode'] == 'Automatic':
            #     if ephem_now > self.weather_report_open_during_evening_time :

            #         self.cool_down_latch = True
            #         self.weather_report_open_during_evening == False
            #         # Things may have changed! So re-checking the weather and such

            #         # Reopening config and resetting all the things.
            #         # This is necessary just in case a previous weather report was done today
            #         # That can sometimes change the timing.
            #         self.astro_events.compute_day_directory()
            #         self.astro_events.calculate_events()

            #         # Run nightly weather report
            #         #self.run_nightly_weather_report()

            #         if not self.open_and_enabled_to_observe and self.weather_report_is_acceptable_to_observe == True:
            #             if (g_dev['events']['Cool Down, Open'] < ephem_now < g_dev['events']['Observing Ends']):
            #                 if time.time() > self.enclosure_next_open_time and self.opens_this_evening < self.config[
            #                     'maximum_roof_opens_per_evening']:
            #                     self.nightly_reset_complete = False
            #                     self.open_enclosure(enc_status, ocn_status)

            #                     if self.open_and_enabled_to_observe:
            #                         self.weather_report_open_during_evening = False
            #                         self.weather_report_is_acceptable_to_observe = True

            #         self.cool_down_latch = False

            # # If the enclosure is meant to shut during the evening
            # obs_win_begin, sunZ88Op, sunZ88Cl, ephem_now = self.astro_events.getSunEvents()
            # if self.weather_report_close_during_evening == True and enc_status['enclosure_mode'] == 'Automatic' and not (self.local_weather_ok == True and self.local_weather_always_overrides_OWM):
            #     if ephem_now > self.weather_report_close_during_evening_time and ephem_now < g_dev['events'][
            #         'Close and Park']:
            #         if enc_status['enclosure_mode'] == 'Automatic':
            #             self.nightly_reset_complete = False
            #             self.weather_report_is_acceptable_to_observe = False
            #             plog("End of Observing Period due to weather. Closing up enclosure early.")

            #             self.open_and_enabled_to_observe = False
            #             self.park_enclosure_and_close()

            #             self.weather_report_close_during_evening = False

            # Do nightly weather report at cool down open
            #if (g_dev['events']['Cool Down, Open'] <= ephem_now < g_dev['events'][
            #    'Observing Ends']) and not self.nightly_weather_report_complete and not g_dev['debug'] and enc_status['enclosure_mode'] == 'Automatic':
                
            #    self.run_nightly_weather_report()
            #    self.nightly_weather_report_complete = True
                # Also make sure nightly reset is switched to go off
            #    self.nightly_reset_complete = False



            # Ordinary opening routine.
            # Do some checks that it isn't meant to be shut.

            #temp_meant_to_be_shut= False
            # if self.weather_report_open_during_evening and self.weather_report_close_during_evening:
            #     if self.weather_report_close_during_evening_time < ephem_now < self.weather_report_open_during_evening_time:
            #         temp_meant_to_be_shut=True

            if ((g_dev['events']['Cool Down, Open'] <= ephem_now < g_dev['events']['Observing Ends']) and (self.weather_report_open_at_start==True or not self.owm_active) and \
                enc_status['enclosure_mode'] == 'Automatic') and not self.cool_down_latch and (self.local_weather_ok == True or (not self.ocn_exists) or (not self.local_weather_active)) and not \
                enc_status['shutter_status'] in ['Software Fault', 'Opening', 'Closing', 'Error']:# and not temp_meant_to_be_shut:

                self.cool_down_latch = True

                if not self.open_and_enabled_to_observe and (self.weather_report_is_acceptable_to_observe or not self.owm_active): # and (self.weather_report_open_during_evening == False or self.local_weather_always_overrides_OWM):

                    if time.time() > self.enclosure_next_open_time and self.opens_this_evening < self.config['maximum_roof_opens_per_evening']:
                        self.nightly_reset_complete = False
                        self.open_enclosure(enc_status, ocn_status)

                self.cool_down_latch = False

            # If in post-close and park era of the night, check those two things have happened!
            if (g_dev['events']['Close and Park'] <= ephem_now < g_dev['events']['Nightly Reset']) \
                    and enc_status['enclosure_mode'] == 'Automatic':

                if not enc_status['shutter_status'] in ['Closed', 'closed']:
                    plog("Found shutter open after Close and Park, shutting up the shutter")
                    self.park_enclosure_and_close()




    def nightly_reset_script(self, enc_status):
        
        if enc_status['enclosure_mode'] == 'Automatic':
            self.park_enclosure_and_close()

        #self.nightly_weather_report_complete=False
        # Set weather report to false because it is daytime anyways.
        self.weather_report_is_acceptable_to_observe=False
        
        events = g_dev['events']
        obs_win_begin, sunZ88Op, sunZ88Cl, ephem_now = self.astro_events.getSunEvents()

        # Reopening config and resetting all the things.
        self.astro_events.compute_day_directory()
        self.astro_events.calculate_events()
        self.astro_events.display_events()
        
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
        #self.nightly_weather_report_complete=False
        self.weather_report_is_acceptable_to_observe=False
        self.weather_report_open_during_evening=False
        self.weather_report_open_during_evening_time=ephem_now
        self.weather_report_close_during_evening=False
        self.weather_report_close_during_evening_time=ephem_now + 86400
        #self.nightly_weather_report_complete=False
        
        self.keep_open_all_night = False
        self.keep_closed_all_night   = False          
        self.open_at_specific_utc = False
        self.specific_utc_when_to_open = -1.0  
        self.manual_weather_hold_set = False
        self.manual_weather_hold_duration = -1.0
        
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

    # def send_to_user(self, p_log, p_level="INFO"):
    #     """ """
    #     url_log = "https://logs.photonranch.org/logs/newlog"
    #     body = json.dumps(
    #         {
    #             "site": self.config["site"],
    #             "log_message": str(p_log),
    #             "log_level": str(p_level),
    #             "timestamp": time.time(),
    #         }
    #     )
    #     try:
    #         response = requests.post(url_log, body, timeout=20)
    #     except Exception:
    #         print("Log did not send, usually not fatal.")

    def park_enclosure_and_close(self):

        self.open_and_enabled_to_observe = False
        g_dev['enc'].close_roof_directly({}, {})
        
        return

    def open_enclosure(self, enc_status, ocn_status, no_sky=False):

        
        flat_spot, flat_alt = g_dev['evnt'].flat_spot_now()
        obs_win_begin, sunZ88Op, sunZ88Cl, ephem_now = self.astro_events.getSunEvents()

        # Only send an enclosure open command if the weather
        if (self.weather_report_is_acceptable_to_observe or not self.owm_active):

            if not g_dev['debug'] and not enc_status['enclosure_mode'] in ['Manual'] and (
                    ephem_now < g_dev['events']['Cool Down, Open']) or \
                    (g_dev['events']['Close and Park'] < ephem_now < g_dev['events']['Nightly Reset']):
                plog("NOT OPENING THE enclosure -- IT IS THE DAYTIME!!")
                #self.send_to_user("An open enclosure request was rejected as it is during the daytime.")
                return
            else:

                try:

                    plog("Attempting to open the roof.")

                    if ocn_status == None:
                        if not enc_status['shutter_status'] in ['Open', 'open','Opening','opening'] and \
                                enc_status['enclosure_mode'] == 'Automatic':# \
                                #and self.weather_report_is_acceptable_to_observe:
                            self.opens_this_evening = self.opens_this_evening + 1

                            g_dev['enc'].open_roof_directly({}, {})
                            # g_dev['enc'].open_command({}, {})


                    elif  not enc_status['shutter_status'] in ['Open', 'open','Opening','opening'] and \
                            enc_status['enclosure_mode'] == 'Automatic' \
                            and time.time() > self.enclosure_next_open_time:#  and self.weather_report_is_acceptable_to_observe:  # NB

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
                        plog("Failed to open roof. Sending the close command to the roof.")
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

    def run_nightly_weather_report(self,enc_status=None):
       
        events = g_dev['events']
        self.weather_report_run_timer=time.time()
        obs_win_begin, sunset, sunrise, ephem_now = self.astro_events.getSunEvents()
        #if self.nightly_weather_report_complete==False:
        self.update_status()
        # First thing to do at the Cool Down, Open time is to calculate the quality of the evening
        # using the broad weather report.
        try: 
            plog("Applsing quality of evening from Open Weather Map.")
            owm = OWM('d5c3eae1b48bf7df3f240b8474af3ed0')
            mgr = owm.weather_manager()            
            one_call = mgr.one_call(lat=self.config["latitude"], lon=self.config["longitude"])
            #self.nightly_weather_report_complete=True
            #breakpoint()
            # Collect relevant info for fitzgerald weather number calculation
            hourcounter=0
            fitzgerald_weather_number_grid=[]
            hours_until_end_of_observing= math.ceil((events['Close and Park'] - ephem_now) * 24)
            hours_until_start_of_observing= math.ceil((events['Cool Down, Open'] - ephem_now) * 24)
            if hours_until_start_of_observing < 0:
                hours_until_start_of_observing = 0
            plog("Hours until end of observing: " + str(hours_until_end_of_observing))
            

            OWM_status_json={}
            OWM_status_json["timestamp"] = round(time.time(), 1)
            for hourly_report in one_call.forecast_hourly:
                
                #if hourcounter > 24:
                #    pass
                #else:
                #breakpoint()
                clock_hour=int(hourly_report.reference_time('iso').split(' ')[1].split(':')[0])


                # Calculate Fitzgerald number for this hour
                tempFn=0
                # Add humidity score up
                if 80 < hourly_report.humidity <= 85:
                    tempFn=tempFn+4
                elif 85 < hourly_report.humidity <= 90:
                    tempFn=tempFn+20
                elif 90 < hourly_report.humidity <= 100:
                    tempFn=tempFn+101

                # Add cloud score up
                if 20 < hourly_report.clouds <= 40:
                    tempFn=tempFn+10
                elif 40 < hourly_report.clouds <= 60:
                    tempFn=tempFn+40
                elif 60 < hourly_report.clouds <= 80:
                    tempFn=tempFn+60
                elif 80 < hourly_report.clouds <= 100:
                    tempFn=tempFn+101

                # Add wind score up
                if 8 < hourly_report.wind()['speed'] <=12:
                    tempFn=tempFn+1
                elif 12 < hourly_report.wind()['speed'] <= 15:
                    tempFn=tempFn+4
                elif 15 < hourly_report.wind()['speed'] <= 20:
                    tempFn=tempFn+40
                elif 20 < hourly_report.wind()['speed'] :
                    tempFn=tempFn+101

                if 'rain'  in hourly_report.detailed_status or 'storm'  in hourly_report.detailed_status:
                    tempFn=tempFn+101

                #breakpoint()
                #
                weatherline=[hourly_report.humidity,hourly_report.clouds,hourly_report.wind()['speed'],hourly_report.status, hourly_report.detailed_status, clock_hour, tempFn, hourly_report.reference_time('iso'), hourly_report.temperature()['temp'] - 273.15, hourly_report.rain]
                fitzgerald_weather_number_grid.append(weatherline)

                hourcounter=hourcounter + 1


            forecast_status=[]
            for weatherline in fitzgerald_weather_number_grid:

                status_line={}
                #breakpoint()
                status_line['humidity']=weatherline[0]
                status_line['cloud_cover'] = weatherline[1]
                status_line['wind_speed'] = weatherline[2]
                status_line['short_text'] = weatherline[3]
                status_line['long_text'] = weatherline[4]
                #breakpoint()
                status_line['utc_clock_hour'] = weatherline[5]
                status_line['fitz_number'] = weatherline[6]
                status_line['utc_long_form'] = weatherline[7].replace(' ','T').split('+')[0]+'Z'
                status_line['temperature'] = weatherline[8]
                status_line['rain'] = weatherline[9]

                if float(weatherline[6]) < 11:
                    status_line['weather_quality_number'] = 1
                elif float (weatherline[6]) < 21:
                    status_line['weather_quality_number'] = 2
                elif float (weatherline[6]) < 41:
                    status_line['weather_quality_number'] = 3
                elif float (weatherline[6]) < 101:
                    status_line['weather_quality_number'] = 4
                else:
                    status_line['weather_quality_number'] = 5

                forecast_status.append(status_line)
                #breakpoint()
                #OWM_status_json[str(hourcounter)] = weatherline
            #plog (fitzgerald_weather_number_grid)    

            #breakpoint()

            if forecast_status is not None:
                lane = "forecast"
                obsy = self.config['wema_name']
                url = f"https://status.photonranch.org/status/{obsy}/status"

                payload = json.dumps({
                    "statusType": "forecast",
                    "status": { "forecast": forecast_status }
                })
                response = requests.request("POST", url, data=payload)
                #print(response.json())

                #breakpoint()


                #try:
                #    send_status(obsy, lane, forecast_status)
                #except:
                #    plog('could not send owm weather status')


            #breakpoint()
            # Fitzgerald weather number calculation.
            hourly_fitzgerald_number=[]
            hourly_fitzgerald_number_by_hour=[]
            hourcounter = 0
            self.hourly_report_holder=[]
            for entry in fitzgerald_weather_number_grid:
                if hourcounter >= hours_until_start_of_observing and hourcounter <= hours_until_end_of_observing:
                    
                    #breakpoint()

                    textdescription= entry[4]+ '   Cloud:   ' + str(entry[1]) + '%     Hum:    ' + str(entry[0]) +   '%    Wind:  ' +str(entry[2])+' m/s      rain: ' + str(entry[9])  # WER changed to make more readable.

                    hourly_fitzgerald_number.append(entry[6])
                    hourly_fitzgerald_number_by_hour.append([entry[5],entry[6],textdescription])
                hourcounter=hourcounter+1
            
            plog ("Hourly Fitzgerald number report")
            self.hourly_report_holder.append("Hourly Fitzgerald number report")
            plog ("*******************************")
            self.hourly_report_holder.append("*******************************")
            plog ("Hour(UTC) |  FNumber |  Text    ")
            self.hourly_report_holder.append("Hour(UTC) |  FNumber |  Text    ")
            for line in hourly_fitzgerald_number_by_hour:
                plog (str(line[0]) + '         | '+ str(line[1]) + '        | ' + str(line[2]))
                self.hourly_report_holder.append(str(line[0]) + '         | '+ str(line[1]) + '        | ' + str(line[2]))
            #plog (hourly_fitzgerald_number_by_hour)
            plog ("Night's total fitzgerald number: " + str(sum(hourly_fitzgerald_number)))
            #plog (sum(hourly_fitzgerald_number))

            #breakpoint()

            self.night_fitzgerald_number = sum(hourly_fitzgerald_number)
            if len(hourly_fitzgerald_number) >= 1:
                average_fitzn_for_rest_of_night = sum(hourly_fitzgerald_number) / len(hourly_fitzgerald_number)
            else:
                average_fitzn_for_rest_of_night = 100
            #breakpoint()
            plog("Night's average fitzgerald number: " + str(average_fitzn_for_rest_of_night))
            #plog(sum(hourly_fitzgerald_number))

            if average_fitzn_for_rest_of_night < 10:
                plog ("This is a good observing night!")
                self.weather_report_is_acceptable_to_observe=True
                self.weather_report_open_at_start=True
                #self.weather_report_open_during_evening=True
                #self.weather_report_open_during_evening_time=ephem_now
                #self.weather_report_close_during_evening=False
                #self.weather_report_close_during_evening_time=ephem_now
            #elif average_fitzn_for_rest_of_night > 40:
            #    plog ("This is a horrible observing night!")
            #    self.weather_report_is_acceptable_to_observe=False
            #    self.weather_report_open_at_start = False
                #self.weather_report_open_during_evening=False
                #self.weather_report_open_during_evening_time=ephem_now
                #self.weather_report_close_during_evening=False
                #self.weather_report_close_during_evening_time=ephem_now
            elif average_fitzn_for_rest_of_night < 18:
                plog ("This is perhaps not the best night, but we will give it a shot!")
                self.weather_report_is_acceptable_to_observe=True
                self.weather_report_open_at_start = True
                #self.weather_report_open_during_evening=True
                #self.weather_report_open_during_evening_time=ephem_now
                #self.weather_report_close_during_evening=False
                #self.weather_report_close_during_evening_time=ephem_now
            else:
                plog ("This is a problematic night, lets check if one part of the night is clearer than the other.")
                TEMPhourly_restofnight_fitzgerald_number=hourly_fitzgerald_number.copy()
                TEMPhourly_nightuptothen_fitzgerald_number=hourly_fitzgerald_number.copy()
                hourly_restofnight_fitzgerald_number=[]   
                hourly_restofnight_fitzgerald_number_averages=[]
                
                for entry in range(len(TEMPhourly_restofnight_fitzgerald_number)):
                    hourly_restofnight_fitzgerald_number.append(sum(TEMPhourly_restofnight_fitzgerald_number))
                    hourly_restofnight_fitzgerald_number_averages.append(sum(TEMPhourly_restofnight_fitzgerald_number)/len(TEMPhourly_restofnight_fitzgerald_number))
                    
                    TEMPhourly_restofnight_fitzgerald_number.pop(0)
                
                plog ("Hourly Fitzgerald Number for the Rest of the Night")
                plog (hourly_restofnight_fitzgerald_number)
                
                                
                
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
                        plog ("Will observe until then then close down enclosure")
                        self.weather_report_is_acceptable_to_observe=True
                        self.weather_report_close_during_evening=True
                        self.weather_report_close_during_evening_time=ephem_now + (clear_until_hour/24)
                        g_dev['events']['Observing Ends'] = ephem_now + (clear_until_hour/24)
                    else:
                        plog ("looks like it is clear until hour " + str(clear_until_hour) )
                        plog ("But that isn't really long enough to rationalise opening the enclosure")
                        self.weather_report_is_acceptable_to_observe=False
                        self.weather_report_close_during_evening=False

                self.weather_report_open_at_start = False
                if clear_until_hour > 3:
                    plog ("Looks like it is clear enough to open the observatory from the beginning.")
                    self.weather_report_open_at_start = True
                elif hourly_fitzgerald_number[0] > 40 and enc_status['enclosure_mode'] == 'Automatic' and not enc_status['shutter_status'] in ['Closed', 'closed'] and self.owm_active:
                    plog ("Looks like the weather gets rough in the first hour, shutting up observatory.")
                    self.park_enclosure_and_close()

                #breakpoint()

                later_clearing_hour=99
                for q in range(len(hourly_restofnight_fitzgerald_number)):
                    #breakpoint()
                    if self.weather_report_open_at_start and self.weather_report_close_during_evening and q < clear_until_hour:
                        pass
                    elif hourly_restofnight_fitzgerald_number[q] < 100 or hourly_restofnight_fitzgerald_number_averages[q] < 40 :
                        #breakpoint()
                        if q > 2:
                            if hourly_fitzgerald_number[q-1] < 41:
                                # Then step backwards until it is a good number
                                #breakpoint()
                                #even_earlier=0


                                plog ("looks like it is clears up after hour " + str(q) )
                                later_clearing_hour=q

                                #plog ("looks like it is clears up after hour " + str(q+1) )
                                #later_clearing_hour=q+1
                                # Just test if there isn't a couple of "bad" hours at the start
                                #breakpoint()
                                number_of_hours_left_after_later_clearing_hour= len(hourly_restofnight_fitzgerald_number) - q
                                break

                if later_clearing_hour != 99:
                    if number_of_hours_left_after_later_clearing_hour > 2:
                        plog ("looks like clears up at hour " + str(later_clearing_hour) )
                        plog ("Will attempt to open/re-open enclosure then.")
                        self.weather_report_open_during_evening=True
                        self.weather_report_open_during_evening_time=ephem_now + (later_clearing_hour/24) 
                    else:
                        plog ("looks like it clears up at hour " + str(later_clearing_hour) )
                        plog ("But there isn't much time after then, so not going to open then. ")
                        self.weather_report_open_during_evening=False
                        
                # if self.weather_report_close_during_evening==True or self.weather_report_open_during_evening==True:
                #     self.weather_report_is_acceptable_to_observe=True
                # else:
                #     self.weather_report_is_acceptable_to_observe=False
                    
                if clear_until_hour==99 and later_clearing_hour ==99:
                    plog ("It doesn't look like there is a clear enough patch to observe tonight")
                    self.weather_report_is_acceptable_to_observe=False
        except Exception as e:
            plog ("OWN failed", e)
            plog ("Usually a connection glitch")
            #plog(traceback.format_exc())
            #breakpoint()

        # However, if the enclosure is under manual control, leave this switch on.
        if self.enc_status_custom==False:
            enc_status = g_dev['enc'].status
        else:
            enc_status = get_enc_status_custom()
        
        #try:
        if enc_status is not None:
            if enc_status['enclosure_mode'] == 'Manual':
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
    #             self.weather_report_open_during_evening=True
    #             self.weather_report_open_during_evening_time=ephem_now
    #             self.weather_report_close_during_evening=False
    #             self.weather_report_close_during_evening_time=ephem_now
    #         elif sum(hourly_fitzgerald_number) > 1000:
    #             plog ("This is a horrible observing night!")
    #             self.weather_report_is_acceptable_to_observe=False
    #             self.weather_report_open_during_evening=False
    #             self.weather_report_open_during_evening_time=ephem_now
    #             self.weather_report_close_during_evening=False
    #             self.weather_report_close_during_evening_time=ephem_now
    #         elif sum(hourly_fitzgerald_number) < 100:
    #             plog ("This is perhaps not the best night, but we will give it a shot!")
    #             self.weather_report_is_acceptable_to_observe=True
    #             self.weather_report_open_during_evening=True
    #             self.weather_report_open_during_evening_time=ephem_now
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
    #                     plog ("Will observe until then then close down enclosure")
    #                     self.weather_report_is_acceptable_to_observe=True
    #                     self.weather_report_close_during_evening=True
    #                     self.weather_report_close_during_evening_time=ephem_now + (clear_until_hour/24)
    #                     g_dev['events']['Observing Ends'] = ephem_now + (clear_until_hour/24)
    #                 else:
    #                     plog ("looks like it is clear until hour " + str(clear_until_hour) )
    #                     plog ("But that isn't really long enough to rationalise opening the enclosure")
    #                     self.weather_report_is_acceptable_to_observe=False
    #                     self.weather_report_close_during_evening=False
    #
    #             if later_clearing_hour != 99:
    #                 if number_of_hours_left_after_later_clearing_hour > 2:
    #                     plog ("looks like clears up at hour " + str(later_clearing_hour) )
    #                     plog ("Will attempt to open/re-open enclosure then.")
    #                     self.weather_report_open_during_evening=True
    #                     self.weather_report_open_during_evening_time=ephem_now + (later_clearing_hour/24)
    #                 else:
    #                     plog ("looks like it clears up at hour " + str(later_clearing_hour) )
    #                     plog ("But there isn't much time after then, so not going to open then. ")
    #                     self.weather_report_open_during_evening=False
    #
    #             # if self.weather_report_close_during_evening==True or self.weather_report_open_during_evening==True:
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
