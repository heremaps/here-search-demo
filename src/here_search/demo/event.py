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

from here_search.demo.api import API
from here_search.demo.entity.endpoint import (
    AutosuggestConfig,
    BrowseConfig,
    DiscoverConfig,
    EndpointConfig,
    LookupConfig,
)
from here_search.demo.entity.intent import (
    FormulatedTextIntent,
    MoreDetailsIntent,
    NoIntent,
    PlaceTaxonomyIntent,
    SearchIntent,
    TransientTextIntent,
)
from here_search.demo.entity.place import PlaceTaxonomyItem
from here_search.demo.entity.request import RequestContext
from here_search.demo.entity.response import LocationResponseItem, LocationSuggestionItem, Response
from here_search.demo.http import HTTPSession


@dataclass
class SearchEvent(metaclass=ABCMeta):
    """
    A search event realizes the fulfilment of a search intent in a certain context:
    It associates a search intent with the action of getting a response for a defined context.
    """

    context: RequestContext

    @abstractmethod
    async def get_response(self, api: API, config: EndpointConfig, session: HTTPSession) -> Response:
        raise NotImplementedError()

    @classmethod
    @abstractmethod
    def from_intent(cls, context: RequestContext, intent: SearchIntent) -> "SearchEvent":
        raise NotImplementedError()


@dataclass
class PartialTextSearchEvent(SearchEvent):
    """
    This SearchEvent class is used to convey keystrokes in the one box search Text form to an App waiting loop
    """

    query_text: str

    async def get_response(self, api: API, config: AutosuggestConfig, session: HTTPSession) -> Response:
        return await api.autosuggest(
            self.query_text,
            self.context.latitude,
            self.context.longitude,
            x_headers=self.context.x_headers,
            session=session,
            lang=self.context.language,
            limit=config.limit,
            termsLimit=config.terms_limit,
        )

    @classmethod
    def from_intent(cls, context: RequestContext, intent: TransientTextIntent) -> "PartialTextSearchEvent":
        assert isinstance(intent, TransientTextIntent)
        return cls(context=context, query_text=intent.materialization)


@dataclass
class TextSearchEvent(SearchEvent):
    """
    This SearchEvent class is used to convey text submissions from the one box search Text form to an App waiting loop
    """

    query_text: str

    async def get_response(self, api: API, config: DiscoverConfig, session: HTTPSession) -> Response:
        return await api.discover(
            self.query_text,
            self.context.latitude,
            self.context.longitude,
            x_headers=self.context.x_headers,
            session=session,
            lang=self.context.language,
            limit=config.limit,
        )

    @classmethod
    def from_intent(cls, context: RequestContext, intent: FormulatedTextIntent) -> "TextSearchEvent":
        assert isinstance(intent, FormulatedTextIntent)
        return cls(context=context, query_text=intent.materialization)


@dataclass
class DetailsSearchEvent(SearchEvent):
    """
    This SearchEvent class is used to convey location response items selections to an App waiting loop
    """

    item: LocationResponseItem

    async def get_response(self, api: API, config: LookupConfig, session: HTTPSession) -> Response:
        return await api.lookup(
            self.item.data["id"],
            x_headers=self.context.x_headers,
            lang=self.context.language,
            session=session,
        )

    @classmethod
    def from_intent(cls, context: RequestContext, intent: MoreDetailsIntent) -> "DetailsSearchEvent":
        assert isinstance(intent, MoreDetailsIntent)
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
            self.item.data["href"],
            x_headers=self.context.x_headers,
            session=session,
        )

    @classmethod
    def from_intent(cls, context: RequestContext, intent: MoreDetailsIntent) -> "FollowUpSearchEvent":
        assert isinstance(intent, MoreDetailsIntent)
        assert intent.materialization.data["resultType"] in ("categoryQuery", "chainQuery")
        return cls(context=context, item=intent.materialization)


@dataclass
class EmptySearchEvent(SearchEvent):
    context: None = None

    async def get_response(self, api: API, config: LookupConfig, session: HTTPSession) -> Response:
        pass

    @classmethod
    def from_intent(cls, context: RequestContext, intent: NoIntent) -> "EmptySearchEvent":
        assert isinstance(intent, NoIntent)
        return cls()


@dataclass
class PlaceTaxonomySearchEvent(SearchEvent):
    """
    This SearchEvent class is used to convey taxonomy selections to an App waiting loop
    """

    item: PlaceTaxonomyItem

    async def get_response(self, api: API, config: BrowseConfig, session: HTTPSession) -> Response:
        return await api.browse(
            self.context.latitude,
            self.context.longitude,
            x_headers=self.context.x_headers,
            session=session,
            lang=self.context.language,
            limit=config.limit,
            **self.item.mapping,
        )

    @classmethod
    def from_intent(cls, context: RequestContext, intent: PlaceTaxonomyIntent) -> "PlaceTaxonomySearchEvent":
        assert isinstance(intent, PlaceTaxonomyIntent)
        return cls(context=context, item=intent.materialization)


class UnsupportedSearchEvent(Exception):
    pass
