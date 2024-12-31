from woob.capabilities.housing import HOUSE_TYPES, POSTS_TYPES


TYPES = {POSTS_TYPES.RENT: 1,
         POSTS_TYPES.SALE: 2,
         POSTS_TYPES.FURNISHED_RENT: 1,
         POSTS_TYPES.VIAGER: 5}

RET = {HOUSE_TYPES.HOUSE: '2',
       HOUSE_TYPES.APART: '1',
       HOUSE_TYPES.LAND: '4',
       HOUSE_TYPES.PARKING: '3',
       HOUSE_TYPES.OTHER: '10'}

BASE_URL = 'https://www.seloger.com'
