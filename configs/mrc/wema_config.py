# -*- coding: utf-8 -*-
"""
Created on Fri Mar 24 19:29:34 2023

@author: obs
"""

# -*- coding: utf-8 -*-
'''

FIRST Created on Fri Aug  2 11:57:41 2019

Refactored on 20230407


@author: wrosing
'''
import json

'''                                                                                                1         1         1       1
         1         2         3         4         5         6         7         8         9         0         1         2       2
12345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678
'''


# NB NB NB json is not bi-directional with tuples (), instead, use lists [], nested if tuples are needed.
degree_symbol = "°"
wema_name = 'mrc'
instance_type = 'wema'


wema_config = {
    #'site': 'mrc',
    'wema_name': 'mrc',
    'instance_type': 'wema',
    
    'obsp_ids': ['mrc1', 'mrc2'],  # a list of the obsp's in an enclosure.  

    'debug_flag': False,   #Need to resolve
    'debug_mode': False,
    'debug_duration_sec': 3600,

    'enclosure_status_check_period': 30,
    'weather_status_check_period': 30,
    'safety_status_check_period': 30,

    'admin_owner_commands_only': False,   #This probably should be True once control is sorted out
    'owner':  ['google-oauth2|112401903840371673242'],  # Wayne  Can be a list

    'host_path':  'Q:/ptr/',
    'plog_path':  'Q:/ptr/mrc/',  # place where night logs can be found.
    'alt_path':  'Q:/ptr/',  # Alternative place for this host to stash misc stuff
    'save_to_alt_path': 'no',
    'archive_path':  'Q:/ptr/',
    'archive_age': 99,  # Number of days to keep files in the local archive before deletion. Negative means never delete
    'aux_archive_path':  None,  # NB NB we might want to put Q: here for MRC
    'wema_is_a_process':  False,          # Note sure yet this is useful
    'wema_hostname': 'MRC-WEMA',   # Prefer the shorter version
    'wema_path':  'Q:/ptr/',  # '/wema_transfer/',

    # 'wema_write_share_path': 'Q:/ptr/',  # Meant to be where Wema puts status data.
    # 'client_read_share_path':  'Q:/ptr/',  # NB these are all very confusing names.
    # 'client_write_share_path': 'Q:/ptr/',

    'site_is_custom':  False,  # Indicates some special code for this site, found at end of config. Set True if SRO
    'name': 'Mountain Ranch Camp Observatory',
    'airport_code': 'SBA',
    'location': 'Near Santa Barbara CA,  USA',
#   'telescope_description': '0m35 f7.2 Planewave CDK',
    'observatory_url': 'https://starz-r-us.sky/clearskies',
    'observatory_logo': None,
    'dedication':  '''
                    Now is the time for all good persons
                    to get out and vote early and often lest
                    we lose charge of our democracy.
                    ''',  # i.e, a multi-line text block supplied by the owner.  Must be careful about the contents for now.
    'location_day_allsky':  None,  # Thus ultimately should be a URL, probably a color camera.
    'location_night_allsky':  None,  # Thus ultimately should be a URL, usually Mono camera with filters.
    'location _pole_monitor': None,  # This probably gets us to some sort of image (Polaris in the North)
    'location_seeing_report': None,  # Probably a path to a jpeg or png graph.

    'TZ_database_name': 'America/Los_Angeles',
    'mpc_code':  'ZZ23',  # This is made up for now.
    'time_offset': -8,     # NB these two should be derived from Python libs so change is automatic
    'timezone': 'PST',
    
    'latitude': 34.459375,  # Decimal degrees, North is Positive
    'longitude': -119.681172,  # Decimal degrees, West is negative
    'elevation': 317.75,    # meters above sea level
    'reference_ambient':  10.0,  # Degrees Celsius.  Alternately 12 entries, one for every - mid month.
    'reference_pressure':  977.83,  # mbar Alternately 12 entries, one for every - mid month.
    
    'obsid_roof_control': False,  # MTF entered this in to remove sro specific code  NB 'site_is_specifc' also deals with this
    'wema_allowed_to_open_roof': True,
    'period_of_time_to_wait_for_roof_to_open': 50,  # seconds - needed to check if the roof ACTUALLY opens.
    'check_time': 300,  # MF's original setting.
    'maximum_roof_opens_per_evening': 4,
    'roof_open_safety_base_time': 15,
    'site_enclosure_default_mode': "Automatic",  # "Manual", "Shutdown", "Automatic"
    'automatic_detail_default': "Enclosure is set to Automatic mode.",

    'observing_check_period': 5,    # How many minutes between weather checks
    'enclosure_check_period': 5,    # How many minutes between enclosure checks
    'auto_eve_bias_dark': True,
    #'auto_midnight_moonless_bias_dark': False,

    'auto_eve_sky_flat': True,
    'eve_sky_flat_sunset_offset': -40.,  # 40 before Minutes  neg means before, + after.
    'eve_cool_down_open': -45.0,
    'morn_close_and_park': 32.0, # How many minutes after sunrise to close. Default 32 minutes = enough time for narrowban
    'auto_morn_sky_flat': True,
    #auto_morn_bias_dark': True,

    # Local weather limits
    'rain_limit': 0,
    'humidity_limit': 85,
    'windspeed_limit': 25,
    'temperature_minus_dewpoint_limit': 2,
    'sky_temperature_limit': -17,
    'cloud_cover_limit': 25,
    'lowest_ambient_temperature': 1,
    'highest_ambient_temperature': 40,
    


    'defaults': {
        'observing_conditions': 'observing_conditions1',
        'enclosure': 'enclosure1',
    },
    'wema_types': ['observing_conditions','enclosure'], 
    'observing_conditions': {
        'observing_conditions1': {
            'ocn_is_custom':  False,  # Indicates some special site code.
            # Intention it is found near bottom of this file.
            'name': 'Weather Station #1',
            'driver': 'ASCOM.SkyAlert.ObservingConditions',
            'share_path_name': None,
            'driver_2': 'ASCOM.SkyAlert.SafetyMonitor',
            'driver_3': None,
            'has_unihedron': False,
            'ocn_has_unihedron':  False,
            'have_local_unihedron': False,     #  Need to add these to setups.
            'uni_driver': 'ASCOM.SQM.serial.ObservingConditions',
            'unihedron_port':  10    #  False, None or numeric of COM port..

            },
        },

    'enclosure': {
        'enclosure1': {
            'name': 'Megawan',
            'driver': 'ASCOM.SkyRoofHub.Dome',    #  Not really a dome for Skyroof!  
            'enclosure_is_directly_connected': False, # True for ECO and EC2, they connect directly to the enclosure, whereas WEMA are different.
            # NB NB NB MF and WER think about this slightly different ways!
            'encl_serves':  ['mnt1', 'mnt2'],
            'enc_is_custom':  False,   #SRO needs sorting, presuambly with this flag.
            'enc_is_dome': False,   #NB NB NB WER Temp Hack
            'enc_is_rolloff': False,
            'rolloff_has_endwall': False,
            'enc_is_clamshell': True,
            'clamshell_is_split':  True,
            'clamshell_rotates': False,
            'clamshell_axis': 'ENE',
            'enc_is_none': False,   #An open-air telescope, on a patio, deck, etc. Presumably uncovered.
            'enc_is_uncovered':  False,  #Presumably a swicth or sensor controls this signal.

        },
    },

}

if __name__ == '__main__':
    '''
    This is a simple test to send and receive via json.
    '''

    j_dump = json.dumps(wema_config)
    site_unjasoned = json.loads(j_dump)
    if str(wema_config) == str(site_unjasoned):
        print('Strings matched.')
    if wema_config == site_unjasoned:
        print('Dictionaries matched.')
