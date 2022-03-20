from aiohttp import ClientSession

from here_search.widgets import OneBoxMap
from here_search.api import Response, base_url, Endpoint
from .query import NearbySimpleParser

from typing import Tuple
import asyncio


class OneBoxCatNearCat(OneBoxMap):
    default_autosuggest_query_params = {'show': 'ontologyDetails,expandedOntologies'}

    async def handle_key_strokes(self):
        """
        This method is called for each key stroke in the one box search Text form.
        """
        async with ClientSession(raise_for_status=True, headers=OneBoxMap.default_headers) as session:

            find_ontology = None
            get_conjunction_mode = NearbySimpleParser(self.language).conjunction_mode_function()

            while True:
                query_text = await self.wait_for_new_key_stroke()
                if query_text is None:
                    break
                if query_text.strip() == '':
                    self.handle_empty_text_submission()
                    find_ontology = None
                    continue

                latitude, longitude = self.get_search_center()
                conjunction_mode, conjunction, query_tail = get_conjunction_mode(query_text)
                autosuggest_resp, top_ontology = await self.get_first_category_ontology(session, query_text, latitude, longitude)
                if conjunction_mode == NearbySimpleParser.Mode.TOKENS:
                    find_ontology = top_ontology
                elif conjunction_mode in (NearbySimpleParser.Mode.TOKENS_SPACES,
                                          NearbySimpleParser.Mode.TOKENS_CONJUNCTION,
                                          NearbySimpleParser.Mode.TOKENS_CONJUNCTION_SPACES):
                    if top_ontology:
                        find_ontology = top_ontology
                elif conjunction_mode == NearbySimpleParser.Mode.TOKENS_INCOMPLETE_CONJUNCTION:
                    if top_ontology:
                        find_ontology = top_ontology
                    autosuggest_resp.data["queryTerms"] = ([{"term": conjunction}] + autosuggest_resp.data["queryTerms"])[:OneBoxMap.default_terms_limit]

                elif conjunction_mode == NearbySimpleParser.Mode.TOKENS_CONJUNCTION_TOKENS:
                    if top_ontology:
                        find_ontology = top_ontology

                    if find_ontology:
                        near_resp, near_ontology = await self.get_first_category_ontology(session, query_tail, latitude, longitude)
                        if near_ontology:
                            # Replace the query below with the calls to Location Graph
                            print(f"LG call: {find_ontology['categories']} near {near_ontology['categories']}")
                            autosuggest_resp = await asyncio.ensure_future(self.api.autosuggest(
                                session,
                                query_text,
                                latitude,
                                longitude,
                                lang=self.get_language(),
                                limit=self.suggestions_limit,
                                termsLimit=self.terms_limit,
                                **self.autosuggest_query_params))
                            ontology_near_ontology = {"title": f"{find_ontology['title']} {conjunction} {near_ontology['title']}",
                                                      "id": f"{find_ontology['id']}:near:{near_ontology['id']}",
                                                      "resultType": "categoryQuery",
                                                      "href": f"{base_url[Endpoint.DISCOVER]}?at={latitude},{longitude}&lang={self.get_language()}&q={query_text}",
                                                      "highlights": {}}
                            autosuggest_resp.data["items"] = ([ontology_near_ontology] + autosuggest_resp.data["items"])[:OneBoxMap.default_results_limit]
                            if near_resp.data["queryTerms"]:
                                autosuggest_resp.data["queryTerms"] = ([{"term": near_resp.data["queryTerms"][0]["term"]}] + autosuggest_resp.data["queryTerms"])[:OneBoxMap.default_terms_limit]

                self.handle_suggestion_list(autosuggest_resp)

    async def get_first_category_ontology(self, session: ClientSession,
                                          query: str, latitude: float, longitude: float) -> Tuple[Response, dict]:
        autosuggest_resp = await asyncio.ensure_future(
            self.api.autosuggest(session,
                                 query,
                                 latitude,
                                 longitude,
                                 lang=self.get_language(),
                                 limit=self.suggestions_limit,
                                 termsLimit=self.terms_limit,
                                 x_headers=None,
                                 **self.autosuggest_query_params))
        for item in autosuggest_resp.data["items"]:
            if item["resultType"] == "categoryQuery" and "relationship" not in item:
                return autosuggest_resp, item
        else:
            return autosuggest_resp, None

    def run(self):
        OneBoxMap.run(self, handle_key_strokes=self.handle_key_strokes)
