from woob.capabilities.housing import HOUSE_TYPES, POSTS_TYPES


QUERY_TYPES = {
    POSTS_TYPES.RENT: {'searchTypeID': '2', 'typeGroupCategoryID': '6'},
    POSTS_TYPES.SALE: {'searchTypeID': '1', 'typeGroupCategoryID': '1'},
    # POSTS_TYPES.SHARING: {},  # There is no special search for shared appartments.
    POSTS_TYPES.FURNISHED_RENT: {'searchTypeID': '2', 'typeGroupCategoryID': '6'},
    POSTS_TYPES.VIAGER: {'searchTypeID': '1', 'typeGroupCategoryID': '4'},
}

QUERY_TYPES_LABELS = {
    'Location': POSTS_TYPES.RENT,
    'Vente': POSTS_TYPES.SALE,
    'Meublé': POSTS_TYPES.FURNISHED_RENT,
    'vente-viager': POSTS_TYPES.VIAGER,
}


FURNISHED_VALUES = {
    'YES': '1',
    'BOTH': '2'
}

QUERY_HOUSE_TYPES_LABELS = {
    'Appartement': HOUSE_TYPES.APART,
    'Maison': HOUSE_TYPES.HOUSE,
    'Parking': HOUSE_TYPES.PARKING,
    'Terrain': HOUSE_TYPES.LAND,
}

QUERY_HOUSE_TYPES = {
    POSTS_TYPES.SALE: {
        HOUSE_TYPES.APART: ['1'],
        HOUSE_TYPES.HOUSE: ['2'],
        HOUSE_TYPES.PARKING: ['7'],
        HOUSE_TYPES.LAND: ['3'],
        HOUSE_TYPES.OTHER: ['4', '5', '6', '8', '9', '10', '11', '12', '13', '14', '98', '105'],
        HOUSE_TYPES.UNKNOWN: ['1', '2', '3', '4', '5', '6', '7', '8', '9', '10', '11', '12', '13', '98', '105']
    },
    POSTS_TYPES.VIAGER: {
        HOUSE_TYPES.APART: ['27'],
        HOUSE_TYPES.HOUSE: ['28'],
        HOUSE_TYPES.PARKING: ['33'],
        HOUSE_TYPES.LAND: [],
        HOUSE_TYPES.OTHER: ['30', '31', '32', '34', '35', '36', '37', '38', '101', '108'],
        HOUSE_TYPES.UNKNOWN: ['27', '28', '30', '31', '32', '33', '34', '35', '36', '37', '38', '101', '108']
    },
    POSTS_TYPES.RENT: {
        HOUSE_TYPES.APART: ['47'],
        HOUSE_TYPES.HOUSE: ['48'],
        HOUSE_TYPES.PARKING: ['53'],
        HOUSE_TYPES.LAND: [],
        HOUSE_TYPES.OTHER: ['50', '51', '52', '54', '55', '56', '57', '58', '102', '109'],
        HOUSE_TYPES.UNKNOWN: ['47', '48', '50', '51', '52', '53', '54', '55', '56', '57', '58', '102', '109']
    },
    POSTS_TYPES.FURNISHED_RENT: {
        HOUSE_TYPES.APART: ['47'],
        HOUSE_TYPES.HOUSE: ['48'],
        HOUSE_TYPES.PARKING: ['53'],
        HOUSE_TYPES.LAND: [],
        HOUSE_TYPES.OTHER: ['50', '51', '52', '54', '55', '56', '57', '58', '102', '109'],
        HOUSE_TYPES.UNKNOWN: ['47', '48', '50', '51', '52', '53', '54', '55', '56', '57', '58', '102', '109']
    }
}
