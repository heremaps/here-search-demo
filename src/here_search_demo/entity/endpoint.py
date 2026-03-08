###############################################################################
#
# Copyright (c) 2023 HERE Europe B.V.
#
# SPDX-License-Identifier: MIT
# License-Filename: LICENSE
#
###############################################################################

from dataclasses import dataclass
from enum import IntEnum


class Endpoint(IntEnum):
    AUTOSUGGEST = 1
    AUTOSUGGEST_HREF = 2
    DISCOVER = 3
    LOOKUP = 4
    BROWSE = 5
    REVGEOCODE = 6


@dataclass
class EndpointConfig:
    DEFAULT_LIMIT = 20
    limit: int | None = DEFAULT_LIMIT


@dataclass
class AutosuggestConfig(EndpointConfig):
    DEFAULT_TERMS_LIMIT = 20
    terms_limit: int | None = DEFAULT_TERMS_LIMIT


@dataclass
class DiscoverConfig(EndpointConfig):
    pass


@dataclass
class BrowseConfig(EndpointConfig):
    pass


@dataclass
class LookupConfig:
    pass


@dataclass
class NoConfig:
    pass


class MetaFactory:
    klass = None
    primitive = (int, float, str, bool, type)

    def __new__(cls, name, bases, namespaces):
        klass = namespaces["klass"]
        if klass in MetaFactory.primitive:
            return klass
        namespaces["__new__"] = cls.__new
        return type(name, bases, namespaces)

    def __new(cls, *args, **kwargs):
        obj = object.__new__(cls.klass)
        obj.__init__(*args[1:], **kwargs)
        return obj


class AutosuggestConfigFactory(metaclass=MetaFactory):
    klass = AutosuggestConfig


class DiscoverConfigFactory(metaclass=MetaFactory):
    klass = DiscoverConfig


class BrowseConfigFactory(metaclass=MetaFactory):
    klass = BrowseConfig
