from src.here_search.entities import Request, Response, Endpoint
from unittest.mock import Mock, patch

expected_response_data = {"a": "b"}
expected_x_headers = {"X-Request-Id": 'userid',
                      "X-Correlation-ID": "correlationId"}

request = Request(endpoint=Endpoint.AUTOSUGGEST,
                  url='url',
                  x_headers={'X-a': 1, 'Y-b': 2},
                  params={'p1': 'v1', 'p2': 'v2'})


def test_request_key():
    request = Request(endpoint=Endpoint.AUTOSUGGEST,
                      url="url",
                      x_headers={'X-a': 1, 'Y-b': 2},
                      params={'p1': 'v1', 'p2': 'v2'})
    assert request.key() == "urlp1v1p2v2"

