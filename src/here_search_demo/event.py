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
from here_search_demo.entity.intent import ActionIntent, SearchIntent
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

    async def get_response(
        self, api: API, config: AutosuggestConfig, session: HTTPSession
    ) -> Response:  # pragma: no cover
        # Runtime API transport path; tests in this suite focus on event routing with mocked backends.
        return await api.autosuggest(
            session=session,
            q=self.query_text,
            latitude=self.context.latitude,
            longitude=self.context.longitude,
            polyline=self.context.polyline,
            width=self.context.width,
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

    async def get_response(
        self, api: API, config: DiscoverConfig, session: HTTPSession
    ) -> Response:  # pragma: no cover
        # Runtime API transport path; tests in this suite focus on event routing with mocked backends.
        return await api.discover(
            session=session,
            q=self.query_text,
            latitude=self.context.latitude,
            longitude=self.context.longitude,
            polyline=self.context.polyline,
            width=self.context.width,
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

    async def send_signal(self, api: API, session: HTTPSession) -> None:  # pragma: no cover
        # Live signal submission path depends on backend behavior and is not exercised in offline unit tests.
        """Send a 'view' signal if the user opted in via share_experience."""
        if not self.context.share_experience or not self.context.user_id:
            return
        try:
            await api.signals(
                session=session,
                resource_id=self.item.data["id"],
                rank=self.item.rank or 0,
                correlation_id=(self.item.resp.x_headers or {}).get("X-Correlation-ID", ""),
                action="here:gs:action:view",
                userId=self.context.user_id,
            )
        except Exception:
            import traceback

            traceback.print_exc()

    async def get_response(self, api: API, config: LookupConfig, session: HTTPSession) -> Response:  # pragma: no cover
        # Runtime API transport path; tests in this suite focus on event routing with mocked backends.
        await self.send_signal(api, session)
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

    async def send_signal(self, api: API, session: HTTPSession) -> None:  # pragma: no cover
        # Live signal submission path depends on backend behavior and is not exercised in offline unit tests.
        """Send a 'view' signal if the user opted in via share_experience."""
        if not self.context.share_experience or not self.context.user_id:
            return
        try:
            await api.signals(
                session=session,
                resource_id=self.item.data["id"],
                rank=self.item.rank or 0,
                correlation_id=(self.item.resp.x_headers or {}).get("X-Correlation-ID", ""),
                action="here:gs:action:view",
                userId=self.context.user_id,
            )
        except Exception:
            import traceback

            traceback.print_exc()

    async def get_response(self, api: API, config: LookupConfig, session: HTTPSession) -> Response:  # pragma: no cover
        # Runtime API transport path; tests in this suite focus on event routing with mocked backends.
        return await super().get_response(api, config, session)


@dataclass
class FollowUpSearchEvent(SearchEvent):
    """
    This SearchEvent class is used to convey query response items selections to an App waiting loop
    """

    item: LocationResponseItem

    async def send_signal(self, api: API, session: HTTPSession) -> None:  # pragma: no cover
        # Live signal submission path depends on backend behavior and is not exercised in offline unit tests.
        """Send a 'view' signal if the user opted in via share_experience."""
        if not self.context.share_experience or not self.context.user_id:
            return
        x_headers = self.context.x_headers or {}
        try:
            signal_kwargs: dict = {"userId": self.context.user_id}
            if "X-AS-Session-ID" in x_headers:
                signal_kwargs["asSessionId"] = x_headers["X-AS-Session-ID"]
            await api.signals(
                session=session,
                resource_id=self.item.data["id"],
                rank=self.item.rank or 0,
                correlation_id=(self.item.resp.x_headers or {}).get("X-Correlation-ID", ""),
                action="here:gs:action:view",
                **signal_kwargs,
            )
        except Exception:
            import traceback

            traceback.print_exc()

    async def get_response(
        self, api: API, config: DiscoverConfig, session: HTTPSession
    ) -> Response:  # pragma: no cover
        # Runtime API transport path; tests in this suite focus on event routing with mocked backends.
        await self.send_signal(api, session)
        return await api.autosuggest_href(
            session=session,
            href=self.item.data["href"],
            polyline=self.context.polyline,
            width=self.context.width,
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

    async def get_response(self, api: API, config: BrowseConfig, session: HTTPSession) -> Response:  # pragma: no cover
        # Runtime API transport path; tests in this suite focus on event routing with mocked backends.
        return await api.browse(
            session=session,
            latitude=self.context.latitude,
            longitude=self.context.longitude,
            polyline=self.context.polyline,
            width=self.context.width,
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


@dataclass
class ActionSearchEvent(SearchEvent):
    """
    This SearchEvent class sends a signal for a LocationResponseItem click
    without performing a lookup.
    """

    item: LocationResponseItem

    async def send_signal(self, api: API, session: HTTPSession) -> None:  # pragma: no cover
        # Live signal submission path depends on backend behavior and is not exercised in offline unit tests.
        """Send a 'view' signal if the user opted in via share_experience."""
        if not self.context.share_experience or not self.context.user_id:
            return
        try:
            await api.signals(
                session=session,
                resource_id=self.item.data["id"],
                rank=self.item.rank or 0,
                correlation_id=(self.item.resp.x_headers or {}).get("X-Correlation-ID", ""),
                action="here:gs:action:view",
                userId=self.context.user_id,
            )
        except Exception:
            import traceback

            traceback.print_exc()

    async def get_response(
        self, api: API, config: EndpointConfig, session: HTTPSession
    ) -> Response | None:  # pragma: no cover
        # Runtime API transport path; tests in this suite focus on event routing with mocked backends.
        await self.send_signal(api, session)
        return None

    @classmethod
    def from_intent(cls, context: RequestContext, intent: ActionIntent) -> "ActionSearchEvent":
        assert intent.kind == "action"
        return cls(context=context, item=intent.materialization)


class UnsupportedSearchEvent(Exception):
    pass
