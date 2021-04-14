
# -*- coding: utf-8 -*-

# Copyright(C) 2012-2021 Budget Insight

# flake8: compatible

from __future__ import unicode_literals

import datetime
from math import floor


# These following two values are found in '/staticweb/31b06785f73ti1714cafa96c8bd3eba79.js'
# in the bmak dictionary.
PUBLIC_API_KEY = 'afSbep8yjnZUjq3aL010jO15Sawj2VZfdYK8uY90uxq'  # bmak['api_public_key']
CS = '0a46G5m17Vrp4o4c'  # bmak['cs']

SENSOR_DATA_CORE = (
    '1.68-1,2,-94,-100,'
    + '%s'
    + ',uaend,11059,20100101,fr,Gecko,0,0,0,0,398206,1476349,1920,1080,1920,1080,523,938,1920,,cpen:0,'
    + 'i1:0,dm:0,cwen:0,non:1,opc:0,fc:1,sc:0,wrc:1,isc:142,vib:1,bat:0,x11:0,x12:1,4853,0.70177237935'
    + '0,809205738174,0,loc:-1,2,-94,-101,do_en,dm_en,t_dis-1,2,-94,-105,0,0,0,0,1112,1112,0;0,0,0,0,9'
    + '03,903,0;0,-1,0,0,3759,3759,0;0,-1,0,0,3630,3630,1;0,-1,0,0,2164,0,1;-1,2,-94,-102,0,0,0,0,1112'
    + ',1112,0;0,0,0,0,903,903,0;0,-1,0,0,3759,3759,1;0,-1,0,0,3630,3630,1;0,-1,0,0,2164,0,1;-1,2,-94,'
    + '-108,-1,2,-94,-110,-1,2,-94,-117,-1,2,-94,-111,-1,2,-94,-109,-1,2,-94,-114,-1,2,-94,-103,-1,2,-'
    + '94,-112,https://www.thetrainline.com/fr-1,2,-94,-115,1,32,32,0,0,0,0,1369,0,'
    + '%d'
    + ',9,17313,0,0,2885,0,0,1369,0,0,'
    + '%s'
    + ',37735,515,1058213677,25543097,PiZtE,75358,86-1,2,-94,-106,9,1-1,2,-94,-119,0,0,200,0,0,200,200,'
    + '0,200,200,0,0,200,200,-1,2,-94,-122,0,0,0,0,1,0,0-1,2,-94,-123,-1,2,-94,-124,-1,2,-94,-126,-1,2,-'
    + '94,-127,11133333331333333333-1,2,-94,-70,-1279939100;-324940575;dis;;true;true;true;-120;true;24;'
    + '24;true;false;1-1,2,-94,-80,5377-1,2,-94,-116,22145328-1,2,-94,-118,93225-1,2,-94,-129,9feb9225ad'
    + '5184a8162588771f441d89e1b7d80189ac0e715d0fdd97d7b0e0e4,1,0,Intel Open Source Technology Center,Me'
    + 'sa DRI Intel(R) HD Graphics (Whiskey Lake 3x8 GT2) ,'
    + '63b8f3d843a1aa3f6c70274ea7c720e02910278be9d61db366c6242af84e0072,28-1,2,-94,-121,;57;13;0'
)


def build_sensor_data():
    date0_ms = get_cf_date()
    sensor_data_header = encode(CS, PUBLIC_API_KEY)[:16]
    date1_hours = str(floor(get_cf_date() / 3600000))
    date2_ms = get_cf_date()

    sensor_data = (
        sensor_data_header + encode(date1_hours, sensor_data_header)
        + SENSOR_DATA_CORE + ';' + str(get_cf_date() - date0_ms) + ';-1;' + str(get_cf_date() - date2_ms)
    )

    return sensor_data


def get_cf_date():
    return floor(datetime.datetime.now().timestamp() * 1000)


def encode(base_text, key):
    """
    js reference: od: function(t,a)

    Given two strings: base_text and key
    If 'key' is not empty, returns 'base_text' where its numeral characters [0, 9] at i-th position are modified using a cyclic shift.
    The number of gross hops for the i-th shift is conditioned by the unicode value of 'key' (i % n)-th character
    """

    if not key:
        return ''

    res = []
    n = len(key)
    for i, char in enumerate(base_text):
        # The characters corresponding to these unicode values range
        # (47, 57) are ['/', '0', '1', ..., '8', '9']
        # using 'rir' function, char1 is modified only if is a number
        # as minimum value is excluded
        res.append(chr(hops_in_range(ord(char), 47, 57, gross_hops=ord(key[i % n]))))

    return ''.join(res)


def hops_in_range(initial_value, minimum, maximum, gross_hops):
    """
    js reference: rir: function(t, a, e, n)

    For an input 'initial_value' satisfying the boundaries defined by minimum and maximum.
    The output 'returned_value' is obtained by making a cyclic shift with (gross_hops % delta) hops
    and skipping the minimum value

    For an input 'initial_value' not satisfying the boundaries constraint, the output 'returned_value'
    is equal to the 'initial_value' (simple return)

    Otherwise it will always return a value in ]min, max]

    simple return      min       <--- delta --->       max      simple return
    --------------------|-------------------------------|--------------------
                                    perform %
    """
    returned_value = initial_value

    if minimum < returned_value <= maximum:
        delta = maximum - minimum
        hops = gross_hops % delta
        returned_value += hops

        if returned_value > maximum:
            returned_value -= delta
    return returned_value
