###############################################################################
#
# Copyright (c) 2023 HERE Europe B.V.
#
# SPDX-License-Identifier: MIT
# License-Filename: LICENSE
#
###############################################################################

from abc import ABCMeta, abstractmethod
from dataclasses import dataclass

from here_search_demo.api import API
from here_search_demo.entity.endpoint import (
    AutosuggestConfig,
    BrowseConfig,
    DiscoverConfig,
    EndpointConfig,
    LookupConfig,
)
from here_search_demo.entity.intent import SearchIntent
from here_search_demo.entity.place import PlaceTaxonomyItem
from here_search_demo.entity.request import RequestContext
from here_search_demo.entity.response import LocationResponseItem, LocationSuggestionItem, Response
from here_search_demo.http import HTTPSession


@dataclass
class SearchEvent(metaclass=ABCMeta):
    """A search event realizes the fulfilment of a search intent in a certain context."""

    context: RequestContext | None

    @abstractmethod
    async def get_response(self, api: API, config: EndpointConfig, session: HTTPSession) -> Response:
        raise NotImplementedError()

    @classmethod
    @abstractmethod
    def from_intent(cls, context: RequestContext | None, intent: SearchIntent) -> "SearchEvent":
        raise NotImplementedError()


@dataclass
class PartialTextSearchEvent(SearchEvent):
    """
    This SearchEvent class is used to convey keystrokes in the one box search Text form to an App waiting loop
    """

    query_text: str

    async def get_response(self, api: API, config: AutosuggestConfig, session: HTTPSession) -> Response:
        return await api.autosuggest(
            session=session,
            q=self.query_text,
            latitude=self.context.latitude,
            longitude=self.context.longitude,
            route=self.context.route,
            all_along=self.context.all_along,
            x_headers=self.context.x_headers,
            lang=self.context.language,
            limit=config.limit,
            termsLimit=config.terms_limit,
        )

    @classmethod
    def from_intent(cls, context: RequestContext, intent: SearchIntent) -> "PartialTextSearchEvent":
        assert intent.kind == "transient_text"
        return cls(context=context, query_text=str(intent.materialization or ""))


@dataclass
class TextSearchEvent(SearchEvent):
    """
    This SearchEvent class is used to convey text submissions from the one box search Text form to an App waiting loop
    """

    query_text: str

    async def get_response(self, api: API, config: DiscoverConfig, session: HTTPSession) -> Response:
        return await api.discover(
            session=session,
            q=self.query_text,
            latitude=self.context.latitude,
            longitude=self.context.longitude,
            route=self.context.route,
            all_along=self.context.all_along,
            x_headers=self.context.x_headers,
            lang=self.context.language,
            limit=config.limit,
        )

    @classmethod
    def from_intent(cls, context: RequestContext, intent: SearchIntent) -> "TextSearchEvent":
        assert intent.kind == "submitted_text"
        return cls(context=context, query_text=str(intent.materialization or ""))


@dataclass
class DetailsSearchEvent(SearchEvent):
    """
    This SearchEvent class is used to convey location response items selections to an App waiting loop
    """

    item: LocationResponseItem

    async def get_response(self, api: API, config: LookupConfig, session: HTTPSession) -> Response:
        return await api.lookup(
            session=session, id=self.item.data["id"], x_headers=self.context.x_headers, lang=self.context.language
        )

    @classmethod
    def from_intent(cls, context: RequestContext, intent: SearchIntent) -> "DetailsSearchEvent":
        assert intent.kind == "details"
        assert intent.materialization.data["resultType"] not in ("categoryQuery", "chainQuery")
        return cls(context=context, item=intent.materialization)


@dataclass
class DetailsSuggestionEvent(DetailsSearchEvent):
    """
    This SearchEvent class is used to convey location suggestion items selections to an App waiting loop
    """

    item: LocationSuggestionItem

    async def get_response(self, api: API, config: LookupConfig, session: HTTPSession) -> Response:
        return await super().get_response(api, config, session)


@dataclass
class FollowUpSearchEvent(SearchEvent):
    """
    This SearchEvent class is used to convey query response items selections to an App waiting loop
    """

    item: LocationResponseItem

    async def get_response(self, api: API, config: DiscoverConfig, session: HTTPSession) -> Response:
        return await api.autosuggest_href(
            session=session,
            href=self.item.data["href"],
            route=self.context.route,
            all_along=self.context.all_along,
            x_headers=self.context.x_headers,
        )

    @classmethod
    def from_intent(cls, context: RequestContext, intent: SearchIntent) -> "FollowUpSearchEvent":
        assert intent.kind == "details"
        assert intent.materialization.data["resultType"] in ("categoryQuery", "chainQuery")
        return cls(context=context, item=intent.materialization)


@dataclass
class EmptySearchEvent(SearchEvent):
    context: None = None

    async def get_response(self, api: API, config: LookupConfig, session: HTTPSession) -> Response:
        pass

    @classmethod
    def from_intent(cls, context: RequestContext | None, intent: SearchIntent) -> "EmptySearchEvent":
        assert intent.kind == "empty"
        return cls()


@dataclass
class PlaceTaxonomySearchEvent(SearchEvent):
    """
    This SearchEvent class is used to convey taxonomy selections to an App waiting loop
    """

    item: PlaceTaxonomyItem

    async def get_response(self, api: API, config: BrowseConfig, session: HTTPSession) -> Response:
        return await api.browse(
            session=session,
            latitude=self.context.latitude,
            longitude=self.context.longitude,
            route=self.context.route,
            all_along=self.context.all_along,
            x_headers=self.context.x_headers,
            lang=self.context.language,
            limit=config.limit,
            **self.item.mapping,
        )

    @classmethod
    def from_intent(cls, context: RequestContext, intent: SearchIntent) -> "PlaceTaxonomySearchEvent":
        assert intent.kind == "taxonomy"
        return cls(context=context, item=intent.materialization)


class UnsupportedSearchEvent(Exception):
    pass
