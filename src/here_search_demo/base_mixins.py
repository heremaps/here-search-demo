from dataclasses import replace
from typing import Protocol, Tuple, runtime_checkable

from here_search_demo.entity.intent import ActionIntent, SearchIntent
from here_search_demo.entity.request import RequestContext
from here_search_demo.entity.response import Response
from here_search_demo.event import (
    PlaceTaxonomySearchEvent,
    SearchEvent,
    TextSearchEvent,
)
from here_search_demo.http import HTTPSession
from here_search_demo.user import DefaultUser, UserProfile


@runtime_checkable
class SearchHead(Protocol):
    """Protocol documenting the response-rendering contract for a search head.

    Any class that overrides these methods can act as a rendering head on top of
    :class:`OneBoxCore`.  ``OneBoxCore`` itself satisfies this protocol via its
    built-in no-op stubs, so structural subtyping requires no explicit registration.

    Override these methods to send results to a different medium (map widgets,
    terminal, REST API response, …).
    """

    def handle_suggestion_list(self, intent: SearchIntent, response: Response) -> None: ...
    def handle_result_list(self, intent: SearchIntent, response: Response) -> None: ...
    def handle_result_details(self, intent: SearchIntent, response: Response) -> None: ...
    def handle_empty_text_submission(self, intent: SearchIntent, response: Response) -> None: ...
    def handle_action(self, intent: ActionIntent, response: Response) -> None: ...
    async def search_events_preprocess(self, session: HTTPSession) -> None: ...


class UserProfileMixin:
    """Composable mixin that binds a :class:`~here_search_demo.user.UserProfile` to any
    :class:`OneBoxCore` subclass.

    Adds personalization (language adaptation, user identity in context) as a side
    concern, independent of any rendering head.  Use cooperative multiple inheritance::

        class MyApp(UserProfileMixin, OneBoxCore):
            ...

    MRO: ``MyApp → UserProfileMixin → OneBoxCore``

    :param user_profile: Optional profile; defaults to :class:`~here_search_demo.user.DefaultUser`.
    :param kwargs: Forwarded to :class:`OneBoxCore`.
    """

    def __init__(
        self,
        user_profile: UserProfile | None = None,
        **kwargs,
    ):
        self.user_profile = user_profile or DefaultUser()
        super().__init__(
            search_center=(
                self.user_profile.current_latitude,
                self.user_profile.current_longitude,
            ),
            language=self.user_profile.preferred_language,
            **kwargs,
        )
        self.preferred_language = self.get_preferred_language()

    async def handle_search_event(self, session: HTTPSession) -> Tuple[SearchIntent, SearchEvent, Response]:
        """Process a single search event and adapt language if needed.

        Overrides :meth:`OneBoxCore.handle_search_event` to call :meth:`adapt_language`
        after full-text or taxonomy searches.
        """
        intent, event, resp = await super().handle_search_event(session)
        if isinstance(event, TextSearchEvent) or isinstance(event, PlaceTaxonomySearchEvent):
            await self.adapt_language(resp)
        return intent, event, resp

    def get_preferred_language(self, country_code: str | None = None) -> str | None:
        if country_code:
            return self.user_profile.get_preferred_country_language(country_code)
        else:
            return self.user_profile.get_current_language()

    @staticmethod
    def _extract_country_code(resp) -> str | None:
        """Return the single country code present across all response items, or None.

        Returns None when items have no countryCode, when countryCode values are
        mixed across items, or when the items list is empty.
        """
        codes = {item.get("address", {}).get("countryCode") for item in resp.data.get("items", [])} - {None}
        return codes.pop() if len(codes) == 1 else None

    async def adapt_language(self, resp) -> None:
        country_code = self._extract_country_code(resp)
        if country_code is None:
            return
        language = self.get_preferred_language(country_code)
        if language and language != self.preferred_language:
            self.preferred_language = language

    def set_search_center(self, latlon: tuple[float, float]) -> None:
        self.search_center = latlon

    def _get_context(self) -> RequestContext:
        ctx = super()._get_context()
        return replace(
            ctx,
            share_experience=self.user_profile.share_experience,
            user_id=self.user_profile.id if self.user_profile.share_experience else None,
        )
