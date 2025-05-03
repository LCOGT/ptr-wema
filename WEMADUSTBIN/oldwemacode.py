# -*- coding: utf-8 -*-
"""
Created on Fri Apr 18 20:28:00 2025

@author: obs
"""

#breakpoint()
# Put in relevant sun and moon potential effects
# line_of_weather_info.append(sun_altitude / u.deg)
# line_of_weather_info.append(moon_altitude/ u.deg)
# line_of_weather_info.append(moon_illumination)
# line_of_weather_info.append(flux_ground)
# line_of_weather_info.append(sun_azimuth / u.deg)



# transformed_sun_altitude= np.exp( max(sun_altitude/ u.deg, -18) / 6.0)

# new_data = pd.DataFrame({
#     #'Humidity': [model_humidity],
#     #'sky_temp_C':  [ocn_status['sky_temp_C']],
#     'transformed_sun_altitude': [transformed_sun_altitude], # below -18, there is no solar flux
    
#     'sun_azimuth': [sun_azimuth/ u.deg],
#     'moon_flux_on_ground': [flux_ground]
# })


# try:
#     predicted_contribution =  self.sky_temp_model.predict(new_data)
    
#     plog ("Predicted skytemp contribution: " + str(predicted_contribution))
    
#     corrected_sky_temp_C = ocn_status['sky_temp_C'] - predicted_contribution[0]

#     plog(f"Corrected Sky Temperature: {corrected_sky_temp_C:.2f} °C")
# except:
#     plog ("Failed to correct sky temperature. Maybe no weather log yet")
#     corrected_sky_temp_C=ocn_status['sky_temp_C']

########## THEN DO CLOUD MODEL


# new_data = pd.DataFrame({
#     #'Humidity': [model_humidity],
#     'corrected_sky_temp_C': corrected_sky_temp_C,
#     'sky-ambient': [model_skyambient],
#     #'dew_point_depression': [model_dewpointdepression],
#     'sky-ambient^2': [model_skyambient **2]
#     #'phase_of_day': [model_phaseofday]
# })


# # Drop irrelevant columns
# df_clean = df.drop(columns=['date', 'time', 'Local_clouds', 'time_in_days', 'time_in_years'], errors='ignore')

# # Check the range of 'phase_of_year'
# if 'phase_of_year' in df_clean.columns:
#     phase_of_year_range = df_clean['phase_of_year'].max() - df_clean['phase_of_year'].min()
# else:
#     phase_of_year_range = 0



    # df['sky-ambientxphase_of_day'] = df['sky-ambient'] * df['phase_of_day']
    # df['sky-ambient^2xphase_of_day'] = df['sky-ambient^2'] * df['phase_of_day']

    # # Add Fourier terms for seasonality
    # df['sin_hour'] = np.sin(2 * np.pi * df['phase_of_day'])
    # df['cos_hour'] = np.cos(2 * np.pi * df['phase_of_day'])
    # df['sin_year'] = np.sin(2 * np.pi * df['phase_of_year'])
    # df['cos_year'] = np.cos(2 * np.pi * df['phase_of_year'])

    # Select features based on the range check
    # if phase_of_year_range > 0.9:
    #     features = ['sky_temp_C', 'sky-ambient',  'sky-ambient^2']#, 'phase_of_day', 'phase_of_year'] 'dew_point_depression',
    # else:
        
        #breakpoint()
        
        # # Only consider the options that agree the best
        # # where the stdev is the lowest (agreement is highest) across the forecasts
        # #breakpoint()
        # cloud_stdev_threshold=np.quantile(np.asarray(region_df['clouds_row_stdev']),0.2)
        # region_df= region_df[(region_df['clouds_row_stdev'] < cloud_stdev_threshold) ] 
            
        
    
        # plt.figure(figsize=(8, 6))
        # plt.scatter(region_df['avg_forecast_cloudcover'], region_df['sky_temp_C'])
        # plt.xlabel('Average Forecast Cloud Cover (%)')
        # plt.ylabel('Sky Temperature (°C)')
        # plt.title('Sky Temperature vs Forecast Cloud Cover')
        # # plt.grid(True)
        # # plt.show()
        
        # plt.savefig(directory + '/' + part_of_day + '/skytempvsclouds_' + str(file_date_string) + '.png', dpi=300, bbox_inches='tight')
        

        #breakpoint()
    
        # plt.figure(figsize=(8, 6))
        # plt.scatter(region_df['avg_forecast_cloudcover'], region_df['sky-ambient'])
        # plt.xlabel('Average Forecast Cloud Cover (%)')
        # plt.ylabel('Sky Temperature - Ambient Temperature (°C)')
        # plt.title('Sky - Ambient Temperature vs Forecast Cloud Cover')
        # # plt.grid(True)
        # plt.show()
        
            
    
        # plt.figure(figsize=(8, 6))
        # plt.scatter(region_df['avg_forecast_cloudcover'], region_df['sky-ambient^2'])
        # plt.xlabel('Average Forecast Cloud Cover (%)')
        # plt.ylabel('Sky-Ambient^2 Temperature (°C)')
        # plt.title('Sky-Ambient^2 Temperature vs Forecast Cloud Cover')
        # # plt.grid(True)
        # # plt.show()
        