###############################################################################
#
# Copyright (c) 2023 HERE Europe B.V.
#
# SPDX-License-Identifier: MIT
# License-Filename: LICENSE
#
###############################################################################


from typing import TypedDict

try:
    from typing import NotRequired
except ImportError:
    from typing_extensions import NotRequired


class CommonDataItemDict(TypedDict):
    resultType: str
    title: str
    id: str


class QueryDataItemDict(CommonDataItemDict):
    href: str
    highlights: dict


class PositionDict(TypedDict):
    lat: float
    lng: float


class DisplayPositionType(PositionDict):
    pass


class AccessPointTypeDict(PositionDict):
    primary: NotRequired[bool]
    label: NotRequired[str]
    type: NotRequired[str]


class LocationDataItemDict(CommonDataItemDict, total=False):
    address: dict
    position: PositionDict
    access: list[AccessPointTypeDict]
    distance: int


class IdDict(TypedDict):
    id: str


class CategoryIdDict(IdDict):
    pass


class SupplierIdDict(IdDict):
    pass


class CategoryDict(CategoryIdDict):
    id: str
    name: str
    primary: NotRequired[bool]


class ChainDict(TypedDict):
    id: str
    name: str


class ImageDict(TypedDict, total=False):
    supplier: SupplierIdDict
    href: str
    date: NotRequired[str]


class ImagesDict(TypedDict):
    items: list[ImageDict]


class EditorialDict(TypedDict, total=False):
    supplier: SupplierIdDict
    href: str
    description: NotRequired[str]
    language: str


class EditorialsDict(TypedDict):
    items: list[EditorialDict]


class RatingDict(TypedDict, total=False):
    supplier: SupplierIdDict
    href: str
    average: float
    count: int


class RatingsDict(TypedDict):
    items: list[EditorialDict]


class MediaDict(TypedDict):
    images: NotRequired[ImagesDict]
    editorials: NotRequired[EditorialDict]
    ratings: NotRequired[RatingsDict]


class ContactInfoDict(TypedDict):
    value: str
    categories: NotRequired[CategoryIdDict]


class ContactDict(TypedDict):
    phone: NotRequired[str]
    fax: NotRequired[str]
    www: NotRequired[str]
    email: NotRequired[str]


class StructuredOpeningHoursDict(TypedDict):
    start: str
    duration: str
    recurrence: str


class OpeningHoursDict(TypedDict):
    isOpen: bool
    structured: list[StructuredOpeningHoursDict]
    text: list[str]
    categories: NotRequired[list[CategoryIdDict]]


class PlaceDataItemDict(LocationDataItemDict, total=False):
    categories: list[CategoryDict]
    chains: NotRequired[list[ChainDict]]
    contacts: NotRequired[list[ContactDict]]
    openingHours: NotRequired[list[OpeningHoursDict]]
    media: NotRequired[MediaDict]


class QueryTermDict(TypedDict):
    term: str
    replaces: str
    start: int
    end: int


class ResponseData(TypedDict):
    items: list[PlaceDataItemDict | LocationDataItemDict | QueryDataItemDict]
    queryTerms: list[QueryTermDict] | None
    _x_headers: dict | None
