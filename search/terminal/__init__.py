from search.core import OneBoxBase
from search.user import UserProfile
from search.api import API, Response, base_url, Endpoint

from typing import Tuple, Awaitable
import asyncio
import contextlib
import sys
import termios
from array import array


class OneBoxConsole(OneBoxBase):

    default_results_limit = 5

    def __init__(self,
                 user_profile: UserProfile,
                 api: API=None,
                 results_limit: int=None,
                 suggestions_limit: int=None,
                 terms_limit: int=None,
                 term_keys: bytes=None,
                 **kwargs):
        self.term_keys = array('B', term_keys)
        self.key_queue = None
        self.line_queue = None
        self.reset()
        OneBoxBase.__init__(self,
                            user_profile,
                            api=api,
                            results_limit=results_limit or OneBoxConsole.default_results_limit,
                            suggestions_limit=suggestions_limit or OneBoxConsole.default_results_limit,
                            terms_limit=len(term_keys))

    def reset(self):
        # TODO: this function needs to be awaited... Check a better way to have the b.run() reantrant
        # Maybe bu centralizing a self.loop and explicitely have all call using it???
        try:
            self.key_queue.join()
            self.line_queue.join()
        except AttributeError:
            pass
        self.keys = array('B')
        self.query_terms = []

    def wait_for_new_key_stroke(self) -> Awaitable:
        return self.key_queue.get()

    def wait_for_submitted_value(self) -> Awaitable:
        return self.line_queue.get()

    def handle_suggestion_list(self, response: Response) -> None:
        """
        Typically called by OneBoxBase.handle_key_strokes()
        :param response:
        :return: None
        """
        self.display_terms(response)
        self.display_suggestions(response)

    def handle_empty_text_submission(self) -> None:
        """
        Typically called by OneBoxBase.handle_key_strokes()
        :param autosuggest_resp:
        :return: None
        """
        self.display_terms({"queryTerms": []})

    def handle_result_list(self, response: Response) -> None:
        """
        Typically called by OneBoxBase.handle_text_submissions()
        :param response:
        :return: None
        """
        out = [f"{'->' :<100s}", ' '*100]
        i = -1
        for i, item in enumerate(response.data["items"]):
            out.append(f'{item["title"]: <100s}')
        for j in range(self.results_limit-i-1):
            out.append(' '*100)
        out.append(f"\r\033[{self.results_limit+2}A")
        print('\n'.join(out), end="")

    def display_terms(self, response: Response):
        self.query_terms = [term['term'].strip() for term in response.data["queryTerms"]]
        terms_line = f'| {" | ".join(self.query_terms)} |'
        print(f'{terms_line: <100s}')

    def display_suggestions(self, response: Response):
        out = []
        i = -1
        for i, item in enumerate(response.data["items"]):
            out.append(f'{item["title"]: <100s}')
        for j in range(self.results_limit-i-1):
            out.append(' '*100)
        out.append(f"\r\033[{self.results_limit+2}A")
        print('\n'.join(out), end="")

    @staticmethod
    @contextlib.contextmanager
    def _raw_mode(file):
        old_attrs = termios.tcgetattr(file.fileno())
        new_attrs = old_attrs[:]
        new_attrs[3] = new_attrs[3] & ~(termios.ECHO | termios.ICANON)
        try:
            termios.tcsetattr(file.fileno(), termios.TCSADRAIN, new_attrs)
            yield
        finally:
            termios.tcsetattr(file.fileno(), termios.TCSADRAIN, old_attrs)

    async def dispath(self):
        """Dispatches keystrokes and aggregated lines to two different queues"""
        with OneBoxConsole._raw_mode(sys.stdin):
            reader = asyncio.StreamReader()
            loop = asyncio.get_event_loop()
            await loop.connect_read_pipe(lambda: asyncio.StreamReaderProtocol(reader), sys.stdin)

            while not reader.at_eof():
                ch = await reader.read(1)
                if not ch or ord(ch) <= 4:
                    await self.key_queue.put(None)
                    await self.line_queue.put(None)
                    break
                if ch == b'\n':
                    await self.line_queue.put(self.keys.tobytes().decode())
                    self.keys = array('B')
                else:
                    try:
                        term_index = self.term_keys.index(ord(ch))
                        try:  # to remove the last word
                            while self.keys.pop() != 32:
                                pass
                        except IndexError:
                            pass
                        self.keys.frombytes(b' ')
                        self.keys.frombytes(self.query_terms[term_index].strip().encode())
                        self.keys.frombytes(b' ')
                    except ValueError:
                        self.keys.frombytes(ch)
                    line = self.keys.tobytes().decode()
                    print(f'-> {line: <100s}')
                    await self.key_queue.put(line)

    async def main(self):
        self.key_queue = asyncio.Queue()
        self.line_queue = asyncio.Queue()
        t1 = asyncio.create_task(self.dispath())
        t2 = asyncio.create_task(self.handle_key_strokes())
        t3 = asyncio.create_task(self.handle_text_submissions())
        await asyncio.gather(t1, t2, t3)

    def run(self):
        self.reset()
        asyncio.run(self.main())
