from aiohttp import ClientSession

from here_search.entity.request import (
    Response,
    ResponseItem,
    RequestContext,
)
from here_search.entity.endpoint import EndpointConfig, AutosuggestConfig, DiscoverConfig, BrowseConfig, LookupConfig
from here_search.entity.intent import (
    SearchIntent,
    TransientTextIntent,
    FormulatedTextIntent,
    PlaceTaxonomyIntent,
    MoreDetailsIntent,
    NoIntent,
)
from here_search.entity.place import PlaceTaxonomyItem
from here_search.api import API

from typing import Optional
from abc import ABCMeta, abstractmethod
from dataclasses import dataclass
import asyncio


@dataclass
class SearchEvent(metaclass=ABCMeta):
    context: RequestContext

    @abstractmethod
    async def get_response(
            self, api: API, config: EndpointConfig, session: ClientSession
    ) -> Response:
        raise NotImplementedError()

    @classmethod
    @abstractmethod
    def from_intent(cls, context: RequestContext, intent: SearchIntent):
        raise NotImplementedError()


@dataclass
class PartialTextSearchEvent(SearchEvent):
    """
    This SearchEvent class is used to convey keystrokes in the one box search Text form to an App waiting loop
    """

    query_text: str

    async def get_response(
            self, api: API, config: AutosuggestConfig, session: ClientSession
    ) -> Response:
        return await asyncio.ensure_future(
            api.autosuggest(
                self.query_text,
                self.context.latitude,
                self.context.longitude,
                x_headers=None,
                session=session,
                lang=self.context.language,
                limit=config.limit,
                termsLimit=config.terms_limit,
            )
        )

    @classmethod
    def from_intent(cls, context: RequestContext, intent: TransientTextIntent):
        assert isinstance(intent, TransientTextIntent)
        return cls(context=context, query_text=intent.materialization)


@dataclass
class TextSearchEvent(SearchEvent):
    """
    This SearchEvent class is used to convey text submissions from the one box search Text form to an App waiting loop
    """

    query_text: str

    async def get_response(
            self, api: API, config: DiscoverConfig, session: ClientSession
    ) -> Response:
        return await asyncio.ensure_future(
            api.discover(
                self.query_text,
                self.context.latitude,
                self.context.longitude,
                x_headers=None,
                session=session,
                lang=self.context.language,
                limit=config.limit,
            )
        )

    @classmethod
    def from_intent(cls, context: RequestContext, intent: FormulatedTextIntent):
        assert isinstance(intent, FormulatedTextIntent)
        return cls(context=context, query_text=intent.materialization)

@dataclass
class PlaceTaxonomySearchEvent(SearchEvent):
    """
    This SearchEvent class is used to convey taxonomy selections to an App waiting loop
    """

    item: PlaceTaxonomyItem

    async def get_response(
            self, api: API, config: BrowseConfig, session: ClientSession
    ) -> Response:
        return await asyncio.ensure_future(
            api.browse(
                self.context.latitude,
                self.context.longitude,
                x_headers=None,
                session=session,
                lang=self.context.language,
                limit=config.limit,
                **self.item.mapping,
            )
        )

    @classmethod
    def from_intent(cls, context: RequestContext, intent: PlaceTaxonomyIntent):
        assert isinstance(intent, PlaceTaxonomyIntent)
        return cls(context=context, item=intent.materialization)


@dataclass
class DetailsSearchEvent(SearchEvent):
    """
    This SearchEvent class is used to convey location response items selections to an App waiting loop
    """

    item: ResponseItem

    async def get_response(
            self, api: API, config: LookupConfig, session: ClientSession
    ) -> Response:
        return await asyncio.ensure_future(
            api.lookup(
                self.item.data["id"],
                x_headers=None,
                lang=self.context.language,
                session=session,
            )
        )

    @classmethod
    def from_intent(cls, context: RequestContext, intent: MoreDetailsIntent):
        assert isinstance(intent, MoreDetailsIntent)
        assert intent.materialization.data["resultType"] not in ("categoryQuery", "chainQuery")
        return cls(context=context, item=intent.materialization)


@dataclass
class FollowUpSearchEvent(SearchEvent):
    """
    This SearchEvent class is used to convey query response items selections to an App waiting loop
    """

    item: ResponseItem

    async def get_response(
            self, api: API, config: DiscoverConfig, session: ClientSession
    ) -> Response:
        return await asyncio.ensure_future(
            api.autosuggest_href(
                self.item.data["href"],
                x_headers=None,
                session=session,
            )
        )

    @classmethod
    def from_intent(cls, context: RequestContext, intent: MoreDetailsIntent):
        assert isinstance(intent, MoreDetailsIntent)
        assert intent.materialization.data["resultType"] in ("categoryQuery", "chainQuery")
        return cls(context=context, item=intent.materialization)


@dataclass
class EmptySearchEvent(SearchEvent):
    context: Optional[None] = None

    async def get_response(
            self, api: API, config: LookupConfig, session: ClientSession
    ) -> Response:
        pass

    @classmethod
    def from_intent(cls, context: RequestContext, intent: NoIntent):
        assert isinstance(intent, NoIntent)
        return cls()


class UnsupportedSearchEvent(Exception):
    pass
