import pandas as pd


def read_data_common(path_file):
    """
    Read Earthquake file and return 2 dataframes.
    :param path_file: path and file name to be read
    :return: sismos  and all_months dataframes

    sismos = ['id', 'date', 'latitude', 'longitude', 'depth', 'mag', 'place',
              'time', 'year', 'month', 'YM', 'magtype', 'mag_int', 'region' ]

    all_months = list of all months from  January 1970 to June 2019
    """
    # get data
    original_data = pd.read_csv(path_file, parse_dates=True)
    original_data['time'] = pd.to_datetime(original_data['time'])  # .astype('datetime64[ns]')
    original_data['date'] = pd.to_datetime([d.date() for d in original_data['time']])
    original_data['hour'] = [d.time() for d in original_data['time']]

    # select columns from original data
    sismos = (original_data[['id', 'date', 'latitude', 'longitude', 'depth', 'mag', 'place', 'time']]
              .sort_values(by=['date']))

    # new datetime columns
    sismos['year'] = pd.DatetimeIndex(sismos['date']).year
    sismos['month'] = pd.DatetimeIndex(sismos['date']).month
    sismos['YM'] = pd.to_datetime(sismos['year'].astype(str) + '-' + sismos['month'].astype(str))

    # Classify magnitude into (low, medium and high)
    custom_magnitudes = ([0., 4., 6, 10.])
    sismos['magtype'] = pd.cut(sismos['mag'], custom_magnitudes, labels=["low", "medium", "high"])

    # Magnitude is classified by its integer number, so we manage just 7 magnitudes
    sismos['mag_int'] = sismos['mag'].map(lambda x: int(x))

    # Divide all records into 4 regions, depending on latitude
    maxlat = sismos['latitude'].max()
    minlat = sismos['latitude'].min()
    quarter = (maxlat - minlat) / 5
    split_latitudes = ([minlat - 1, minlat + quarter, minlat + (2 * quarter), minlat + (3 * quarter), maxlat + 1])
    sismos['region'] = pd.cut(sismos['latitude'], split_latitudes,
                              labels=["Patagonia", "Puerto Mont", "Santiago", 'Atacama'])

    # Dummy dataframe with all months from 1970 until 2019
    all_months = pd.DataFrame()
    all_months['YM'] = pd.date_range(start='1/1/1970', end='6/1/2019', freq='MS')

    return sismos, all_months


def read_data_classification(sismos, all_months, path_file):
    """
    Read Temperature file and return a Dataframe and a Series
    :param sismos: ['id', 'date', 'latitude', 'longitude', 'depth', 'mag', 'place',
                    'time', 'year', 'month', 'YM', 'magtype', 'mag_int', 'region' ]
    :param all_months: list of all months from  January 1970 to June 2019
    :param path_file: path and name of temperature file
    :return: features_classification and  label_classification

    features_classification = ['YM', '2', '3', '4', '5', '6', '7', '8', 'Tempt', 'TemptUncert']
                            where YM reference to month/year
                            and '2', '3', '4', '5', '6', '7', '8' contain the number of earthquakes of that magnitude

    label_classification = 1 if (next month has earthquakes > = 6) else is 0,
    so if a know the earthquakes magnitudes and temperatures of the current month, then I can predict next month
    """

    # Read Temperature fil
    temperature = pd.read_csv(path_file)
    temperature_chile = temperature[temperature['Country'] == 'Chile'][1484:]
    temperature_chile['dt'] = pd.to_datetime(temperature_chile['dt'])

    # Frequency of each integer magnitude per month/year
    sismos_classification = (sismos[['YM', 'mag_int', 'time']].groupby(['YM', 'mag_int'])
                             .agg(['count'])
                             .unstack(fill_value=0).stack()
                             .reset_index()
                             .sort_index())
    sismos_classification.columns = ['YM', 'mag_int', 'count']

    # Fill missing months
    all_sismos_classification = (all_months
                                 .merge(sismos_classification, left_on='YM', right_on='YM', how='left')
                                 .fillna(0))

    # Create one column per integer magnitude, the values of these columns is the number of earthquakes of that kind
    # in the corresponding period
    features_classification = (all_sismos_classification
                               .pivot(index='YM', columns='mag_int', values='count')
                               .fillna(0)
                               .astype(object)
                               .reset_index())
    del features_classification[0.0]

    features_classification.columns = ('YM', '2', '3', '4', '5', '6', '7', '8')

    # Merge Earthquake data with temperature data and select and rename columns
    features_classification = features_classification.merge(temperature_chile, left_on='YM', right_on='dt', how='left')
    features_classification = features_classification[
        ['YM', '2', '3', '4', '5', '6', '7', '8', 'AverageTemperature', 'AverageTemperatureUncertainty']]
    features_classification.columns = ('YM', '2', '3', '4', '5', '6', '7', '8', 'Tempt', 'TemptUncert')

    # I haven't found data for all years, so I decide to set missing values with the mean for the same month
    features_classification['Month'] = features_classification['YM'].map(lambda x: x.month)
    temp_mean = (features_classification
                 .groupby(features_classification['YM'].map(lambda x: x.month)).mean())
    features_classification = features_classification.merge(temp_mean, left_on='Month', right_index=True, how='left')
    features_classification['Tempt_x'].fillna(features_classification['Tempt_y'], inplace=True)
    features_classification['TemptUncert_x'].fillna(features_classification['TemptUncert_y'], inplace=True)
    del features_classification['Month_x']
    del features_classification['Tempt_y']
    del features_classification['TemptUncert_y']
    del features_classification['Month_y']
    features_classification.columns = ('YM', '2', '3', '4', '5', '6', '7', '8', 'Tempt', 'TemptUncert')

    # Make discrete 'Tempt' and 'TemptUncert' columns
    features_classification['Tempt'] = round(features_classification['Tempt'], 1)
    features_classification['TemptUncert'] = round(features_classification['TemptUncert'], 1)

    # Convert to integer columns type object
    columns_object = features_classification.columns[features_classification.dtypes == 'object']
    for column_object in columns_object:
        features_classification[column_object] = features_classification[column_object].astype('int')

    # label_classification = what we want to predict it's if the next month will have a big earthquake depending on
    # earthquake during current month and temperatures.'''
    # So first we calculate if the current month has a big earthquake
    label_classification = (features_classification
                            .apply(lambda r: 0 if ((r['6'], r['7'], r['8']) == (0, 0, 0)) else 1, axis=1))
    # Second we move them to their previous index and set 0 to the last month
    label_classification = label_classification.shift(-1).fillna(0).astype('int')

    return features_classification, label_classification


def read_data_time_series(sismos, all_months):
    """
    Return required DataFrames for Time Series Analysis
    :param sismos: ['id', 'date', 'latitude', 'longitude', 'depth', 'mag', 'place',
                    'time', 'year', 'month', 'YM', 'magtype', 'mag_int', 'region' ]
    :param all_months: list of all months from  January 1970 to June 2019
    :return: frequency_year, time_series_magnitude

    frequency_year = frecuency of earthquakes per year and magnitude type where magtype is
                    {low: mag in [0,4), medium: mag in [4,6), high: mag in [6,10)}
                            low --> you don't notice them
                            medium --> they are not scary
                            high --> the thing would get serious
                    columns = ['year', 'magtype', 'magcount', 'magmax']

    time_series_magnitude =  time series (frequency = month/yeam, data = maximum magnitude per period)
            """

    frequency_year = (sismos[['year', 'magtype', 'mag']]
                      .groupby(['year', 'magtype'])
                      .agg(['count', 'max'])
                      .unstack(fill_value=0).stack()
                      .reset_index()
                      .sort_index()
                      )

    # Update columns name to have just one level ['year', 'magtype', 'magcount', 'magmax']
    frequency_year.columns = [''.join(x) for x in frequency_year.columns.ravel()]

    # Auxiliar DataFrame to create time_series_magnitude = max magnitude per month/year
    aux = (sismos[['YM', 'mag']].groupby(['YM']).max().sort_index())

    time_series_magnitude = (all_months.merge(aux, left_on='YM', right_index=True, how='left')
                             .fillna(aux['mag'].mean())
                             .set_index(all_months['YM'])
                             .sort_index())

    del time_series_magnitude["YM"]

    return frequency_year, time_series_magnitude
