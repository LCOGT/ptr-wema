# -*- coding: utf-8 -*-
'''

Created on Fri Feb 07,  11:57:41 2020
Updated 20220914 WER   This version does not support color camera channel.

@author: wrosing

NB NB NB  If we have one config file then paths need to change depending upon which host does what job.
'''

#                                                                                                  1         1         1
#        1         2         3         4         5         6         7         8         9         0         1         2
#23456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890
import json
import time
#import ptr_events
from pprint import pprint


g_dev = None


#THis is branch wer-mrc first entered here 20221029:21:40 on WEMA
degree_symbol = "°"
site_name = 'aro'
site_config = {

    'site': 'aro', #TIM this may no longer be needed.
    'site_id': 'aro',
    'obs_id': None,
    'observatory_location': site_name.lower(),
    
    'debug_site_mode': False,
    
    'debug_mode': False,
    'admin_owner_commands_only': False,
    'debug_duration_sec': 3600,

    'owner':  ['google-oauth2|102124071738955888216', \
               'google-oauth2|112401903840371673242'],  # Neyle,
    'owner_alias': ['ANS', 'WER', 'TELOPS'],
    'admin_aliases': ["ANS", "WER", 'KVH', "TELOPS", "TB", "DH", "KVH", 'KC'],

    'site_desc': "Apache Ridge Observatory, Santa Fe, NM, USA. 2194m",
    'airport_codes':  ['SAF', 'ABQ', 'LSN'],
    'obsy_id': 'aro1',
    'obs_desc': "0m3f4.9/9 Ceravolo Astrograph, AP1600",
    'debug_site_mode': False,
    'debug_obsy_mode': False,

    'client_hostname':"ARO-0m35",     # Generic place for this host to stash.
    
    'client_path': 'F:/ptr/',
    'alt_path': '//house-computer/saf_archive_2/archive/sq01/',
    'save_to_alt_path' : 'no',
    'archive_path': 'F:/ptr/',       # Where images are kept.
    'local_calibration_path': 'F:/ptr/', # THIS FOLDER HAS TO BE ON A LOCAL DRIVE, not a network drive due to the necessity of huge memmap files
    
    'archive_age' : -99.9, # Number of days to keep files in the local archive before deletion. Negative means never delete
        'send_files_at_end_of_night' : 'no', # For low bandwidth sites, do not send up large files until the end of the night. set to 'no' to disable
        'save_raw_to_disk' : True, # For low diskspace sites (or just because they aren't needed), don't save a separate raw file to disk after conversion to fz.
        'keep_reduced_on_disk' : True, # PTR uses the reduced file for some calculations (focus, SEP, etc.). To save space, this file can be removed after usage or not saved.
        'keep_focus_images_on_disk' : True, # To save space, the focus file can not be saved.
        
        # Minimum realistic seeing at the site.
        # This allows culling of unphysical results in photometry and other things
        # Particularly useful for focus
        'minimum_realistic_seeing' : 1.0,
    
    'aux_archive_path':  None,
    'wema_is_active':  True,     # True if an agent (ie a wema) is used at a site.   # Wemas are split sites -- at least two CPS's sharing the control.
    'wema_hostname':  'ARO-WEMA',
    'wema_path': 'C:/ptr/',      #Local storage on Wema disk.
    'dome_on_wema':  True,       #NB NB NB CHange this confusing name. 'dome_controlled_by_wema'
    'site_IPC_mechanism':  'shares',   # ['None', shares', 'shelves', 'redis']
    'wema_write_share_path':  'C:/ptr/wema_transfer/',  # Meant to be where Wema puts status data.
    'client_write_share_path':  '//aro-wema/wema_transfer/', #Meant to be a share written to by the TCS computer
    'redis_ip': None,   # None if no redis path present, localhost if redis iself-contained
    'site_is_generic':  False,   # A simple single computer ASCOM site.
    'site_is_specific':  False,  #  Meaning like SRO with site specific methods to read weatehr and roof status
    'site_is_custom':  False, 
    'site_has_proxy': True',
    
    'host_wema_site_name':  'ARO',
    
    'name': 'Apache Ridge Observatory 0m3f4.9/9',

    'location': 'Santa Fe, New Mexico,  USA',
    'observatory_url': 'https://starz-r-us.sky/clearskies2',   # This is meant to be optional
    'observatory_logo': None,   # I expect
    'dedication':   '''
                    Now is the time for all good persons
                    to get out and vote, lest we lose
                    charge of our democracy.
                    ''',    # i.e, a multi-line text block supplied and formatted by the owner.
    'location_day_allsky':  None,  #  Thus ultimately should be a URL, probably a color camera.
    'location_night_allsky':  None,  #  Thus ultimately should be a URL, usually Mono camera with filters.
    'location _pole_monitor': None,  #This probably gets us to some sort of image (Polaris in the North)
    'location_seeing_report': None,  # Probably a path to

    'TZ_database_name':  'America/Denver',
    'mpc_code':  'ZZ24',    # This is made up for now.
    'time_offset':  -6.0,   # These two keys may be obsolete give the new TZ stuff
    'timezone': 'MDT',      # This was meant to be coloquial Time zone abbreviation, alternate for "TX_data..."
    'latitude': 35.554298,     # Decimal degrees, North is Positive
    'longitude': -105.870197,   # Decimal degrees, West is negative
    'elevation': 2194,    # meters above sea level
    'reference_ambient':  10.0,  # Degrees Celsius.  Alternately 12 entries, one for every - mid month.
    'reference_pressure':  794.0,    #mbar   A rough guess 20200315

    'obsid_roof_control':False, #MTF entered this in to remove sro specific code.... Basically do we have control of the roof or not see line 338 sequencer.py
    'wema_allowed_to_open_roof': True,
    'period_of_time_to_wait_for_roof_to_open' : 50, # seconds - needed to check if the roof ACTUALLY opens. 
    'only_scope_that_controls_the_roof': True, # If multiple scopes control the roof, set this to False
    'check_time': 300,
    'maximum_roof_opens_per_evening' : 4,
    'roof_open_safety_base_time' : 15, # How many minutes to use as the default retry time to open roof. This will be progressively multiplied as a back-off function.
    
    'closest_distance_to_the_sun': 45, # Degrees. For normal pointing requests don't go this close to the sun. 
    'closest_distance_to_the_moon': 10, # Degrees. For normal pointing requests don't go this close to the moon. 
    'lowest_requestable_altitude': -5, # Degrees. For normal pointing requests don't allow requests to go this low. 
    
    
    'site_enclosure_default_mode': "Automatic",   # ["Manual", "Shutdown", "Automatic"]
    
    'automatic_detail_default': "Enclosure is initially set to Automatic by ARO site_config.",
    'observing_check_period' : 2,    # How many minutes between weather checks
    'enclosure_check_period' : 2,    # How many minutes between enclosure checks
    'auto_eve_bias_dark': True,
    
    'auto_midnight_moonless_bias_dark': False,
    'auto_eve_sky_flat': True,
    'eve_sky_flat_sunset_offset': -60.0,  # Minutes  neg means before, + after.
    'eve_cool_down_open' : -65.0,
    'auto_morn_sky_flat': True,
    'auto_morn_bias_dark': True,
    're-calibrate_on_solve': True,
    'pointing_calibration_on_startup': False,
    'periodic_focus_time' : 0.5, # This is a time, in hours, over which to bypass automated focussing (e.g. at the start of a project it will not refocus if a new project starts X hours after the last focus)
    'stdev_fwhm' : 0.5, # This is the expected variation in FWHM at a given telescope/camera/site combination. This is used to check if a fwhm is within normal range or the focus has shifted
    'focus_exposure_time': 15, # Exposure time in seconds for exposure image
    'pointing_exposure_time': 20, # Exposure time in seconds for exposure image
    'focus_trigger' : 0.5, # What FWHM increase is needed to trigger an autofocus
    'solve_nth_image' : 6, # Only solve every nth image
    'solve_timer' : 4, # Only solve every X minutes
    'threshold_mount_update' : 10, # only update mount when X arcseconds away
    'get_ocn_status': None,
    'get_enc_status': None,
    'not_used_variable': None,



    'defaults': {
        'observing_conditions': 'observing_conditions1',  # These are used as keys, may go away.
        'enclosure': 'enclosure1',
        'screen': 'screen1',
        'mount': 'mount1',
        'telescope': 'telescope1',     #How do we handle selector here, if at all?
        'focuser': 'focuser1',
        'rotator': 'rotator1',
        'selector': None,
        'filter_wheel': 'filter_wheel1',
        'camera': 'camera_1_1',
        'sequencer': 'sequencer1'
        },
    'device_types': [
        'observing_conditions',
        'enclosure',
        'mount',
        'telescope',
        # 'screen',
        'rotator',
        'focuser',
        'selector',
        'filter_wheel',
        'camera',
        'sequencer',
        ],
    'wema_types': [
       'observing_conditions',
       'enclosure',
       ],
    'enc_types': [
        'enclosure'
    ],
    'short_status_devices':  [
       'mount',
       'telescope',
       # 'screen',
       'rotator',
       'focuser',
       'selector',
       'filter_wheel',
       'camera',
       'sequencer',
       ],

    'wema_status_span':  ['aro'],

    'observing_conditions' : {     #for SAF
        'observing_conditions1': {
            'parent': 'site',
            'ocn_is_specific':  False, 
            'name': 'Boltwood',
            'driver': 'ASCOM.Boltwood.ObservingConditions',
            'driver_2':  'ASCOM.Boltwood.OkToOpen.SafetyMonitor',
            'driver_3':  'ASCOM.Boltwood.OkToImage.SafetyMonitor',
            'redis_ip': '127.0.0.1',   #None if no redis path present
            'has_unihedron':  True,
            'have_local_unihedron': False,  
            'uni_driver': 'ASCOM.SQM.serial.ObservingConditions',
            'unihedron_port':  10    # False, None or numeric of COM port.
        },
    },

    'enclosure': {
        'enclosure1': {
            'parent': 'site',

            'name': 'HomeDome',
            'enc_is_specific':  False,
            
            'directly_connected': False, # For ECO and EC2, they connect directly to the enclosure, whereas WEMA are different.
            'hostIP':  '10.0.0.10',
            'driver': 'ASCOM.Dragonfly.Dome',  #  'ASCOMDome.Dome',  #ASCOMDome.Dome',  # ASCOM.DeviceHub.Dome',  # ASCOM.DigitalDomeWorks.Dome',  #"  ASCOMDome.Dome',

            'has_lights':  True,
            'controlled_by': 'mount1',
			'is_dome': True,
            'mode': 'Automatic',
            'enc_radius':  70,  #  inches Ok for now.
            'common_offset_east': -19.5,  # East is negative.  These will vary per telescope.
            'common_offset_south': -8,  # South is negative.   So think of these as default.

            'cool_down': 89.0,     # Minutes prior to sunset.
            'settings': {
                'lights':  ['Auto', 'White', 'Red', 'IR', 'Off'],       #A way to encode possible states or options???
                                                                        #First Entry is always default condition.
                'roof_shutter':  ['Auto', 'Open', 'Close', 'Lock Closed', 'Unlock'],
            },
            'eve_bias_dark_dur':  1.5,   # hours Duration, prior to next.
            'eve_screen_flat_dur': 0.0,   # hours Duration, prior to next.
            'operations_begin':  -1.0,   # - hours from Sunset
            'eve_cooldown_offset': -.99,   # - hours beforeSunset
            'eve_sky_flat_offset':  1,   # - hours beforeSunset   Only THis is used in PTR events
            'morn_sky_flat_offset':  0.4,   # + hours after Sunrise
            'morning_close_offset':  0.41,   # + hours after Sunrise
            'operations_end':  0.42,
        },
    },

}


if __name__ == '__main__':
    j_dump = json.dumps(site_config)
    site_unjasoned = json.loads(j_dump)
    if str(site_config)  == str(site_unjasoned):
        print('Strings matched.')
    if site_config == site_unjasoned:
        print('Dictionaries matched.')