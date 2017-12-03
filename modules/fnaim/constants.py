from weboob.capabilities.housing import HOUSE_TYPES, POSTS_TYPES

QUERY_TYPES = {
    POSTS_TYPES.RENT: 2,
    POSTS_TYPES.SALE: 1,
    POSTS_TYPES.SHARING: 2  # There is no special search for shared appartments.
}

QUERY_HOUSE_TYPES = {
    HOUSE_TYPES.APART: [1],
    HOUSE_TYPES.HOUSE: [2],
    HOUSE_TYPES.PARKING: [7],
    HOUSE_TYPES.LAND: [8],
    HOUSE_TYPES.OTHER: [3, 4, 5, 6, 9, 10, 11],
    HOUSE_TYPES.UNKNOWN: range(1, 12)
}
