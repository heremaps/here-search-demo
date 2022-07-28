from here_search.base import OneBoxBase
from here_search.user import Profile
from here_search.entities import Response

from typing import Awaitable, Callable, Union
import asyncio
import contextlib
import sys
import termios
from array import array
from dataclasses import dataclass


@dataclass
class KeyStroke:
    ch: bytes
    keys: array
    query_terms: list
    term_keys: array
    key_queue: asyncio.Queue
    line_queue: asyncio.Queue

    async def side_effect(self) -> None:
        self.keys.frombytes(self.ch)
        line = self.get_line()
        if line:
            print(f'> {line: <100s}', flush=True)
            await self.send_keys(line)

    def get_line(self) -> str:
        decoded = []
        for b in self.keys.tobytes():
            try:
                decoded.append(chr(b))
            except UnicodeDecodeError:
                continue
        return ''.join(decoded)

    async def send_keys(self, keys: Union[str, None]):
        if keys != '':
            await self.key_queue.put(keys)

    async def send_line(self, line: Union[str, None]):
        if line != '':
            await self.line_queue.put(line)


class EOFKeyStroke(KeyStroke):
    async def side_effect(self) -> None:
        await self.send_keys(None)
        await self.send_line(None)
        raise OneBoxConsoleExit()


class EnterKeyStroke(KeyStroke):
    async def side_effect(self) -> None:
        line = self.get_line()
        if line:
            await self.line_queue.put(line)
        self.keys = self.keys[:0]


class DeleteKeyStroke(KeyStroke):
    async def side_effect(self) -> None:
        self.keys.pop()
        line = self.get_line()
        print(f'> {line: <100s}', flush=True)
        await self.send_keys(line)


class TermsKeyStroke(KeyStroke):
    async def side_effect(self) -> None:
        self.replace_last_term()
        line = self.keys.tobytes().decode()
        print(f'> {line: <100s}', flush=True)
        if line:
            await self.key_queue.put(line)

    def replace_last_term(self) -> None:
        term_index = self.term_keys.index(ord(self.ch))
        try:  # to remove the last word
            while self.keys.pop() != 32:
                pass
        except IndexError:
            pass
        self.keys.frombytes(b' ')
        self.keys.frombytes(self.query_terms[term_index].strip().encode())
        self.keys.frombytes(b' ')


class ItemsKeyStroke(KeyStroke):
    async def side_effect(self) -> None:
        pass


class OneBoxConsoleExit(Exception):
    pass


class OneBoxConsole(OneBoxBase):
    term_keys: array
    key_queue: asyncio.Queue
    line_queue: asyncio.Queue
    keys: array
    query_terms: list

    default_results_limit = 5

    def __init__(self,
                 user_profile: Profile,
                 results_limit: int=None,
                 suggestions_limit: int=None,
                 term_keys: bytes=None,
                 item_keys: bytes=None,
                 **kwargs):
        self.term_keys = array('B', term_keys)
        self.item_keys = array('B', item_keys)
        self.key_queue = None
        self.line_queue = None
        self.reset()
        OneBoxBase.__init__(self,
                            user_profile,
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
        self.display_terms(Response(data={"queryTerms": []}))

    def handle_result_list(self, response: Response) -> None:
        """
        Typically called by OneBoxBase.handle_text_submissions()
        :param response:
        :return: None
        """
        print('\n'.join(f"{i: 2}: {item['title']}" for i, item in enumerate(response.data["items"])), flush=True)

    def display_terms(self, response: Response) -> None:
        self.query_terms = [term['term'].strip() for term in response.data["queryTerms"]]
        print(", ".join(self.query_terms), flush=True)

    def display_suggestions(self, response: Response) -> None:
        self.handle_result_list(response)

    @staticmethod
    @contextlib.contextmanager
    def _raw_mode(file):
        # https://stackoverflow.com/a/65909044/1221746
        old_attrs = termios.tcgetattr(file.fileno())
        new_attrs = old_attrs[:]
        new_attrs[3] = new_attrs[3] & ~(termios.ECHO | termios.ICANON)
        try:
            termios.tcsetattr(file.fileno(), termios.TCSADRAIN, new_attrs)
            yield
        finally:
            termios.tcsetattr(file.fileno(), termios.TCSADRAIN, old_attrs)

    def get_key_stroke(self, ch: bytes):
        if not ch or ord(ch) <= 4:
            return EOFKeyStroke(ch, self.keys, self.query_terms, self.term_keys, self.key_queue, self.line_queue)

        if ch == b'\n':
            return EnterKeyStroke(ch, self.keys, self.query_terms, self.term_keys, self.key_queue, self.line_queue)

        if ch == b'\x7f':
            return DeleteKeyStroke(ch, self.keys, self.query_terms, self.term_keys, self.key_queue, self.line_queue)

        if ord(ch) in self.term_keys:
            return TermsKeyStroke(ch, self.keys, self.query_terms, self.term_keys, self.key_queue, self.line_queue)

        if ord(ch) in self.item_keys:
            return ItemsKeyStroke(ch, self.keys, self.query_terms, self.term_keys, self.key_queue, self.line_queue)

        return KeyStroke(ch, self.keys, self.query_terms, self.term_keys, self.key_queue, self.line_queue)

    async def dispatch(self):
        """Dispatches keystrokes and aggregated lines to two different queues"""
        with OneBoxConsole._raw_mode(sys.stdin):
            # https://stackoverflow.com/a/39085785/1221746
            # https://stackoverflow.com/a/11919074/1221746
            # https://stackoverflow.com/questions/35223896/listen-to-keypress-with-asyncio
            reader = asyncio.StreamReader()
            loop = asyncio.get_event_loop()
            await loop.connect_read_pipe(lambda: asyncio.StreamReaderProtocol(reader), sys.stdin)

            while not reader.at_eof():
                ch = await reader.read(1)
                key = self.get_key_stroke(ch)
                try:
                    await key.side_effect()
                except OneBoxConsoleExit:
                    break

    async def main(self):
        self.key_queue = asyncio.Queue()
        self.line_queue = asyncio.Queue()
        t1 = asyncio.create_task(self.dispatch())
        t2 = asyncio.create_task(self.handle_key_strokes())
        t3 = asyncio.create_task(self.handle_text_submissions())

        await asyncio.gather(t1, t2, t3)

    def run(self,
            handle_user_profile_setup: Callable=None,
            handle_key_strokes: Callable=None,
            handle_text_submissions: Callable=None,
            handle_result_selections: Callable=None):
        self.reset()
        asyncio.run(self.main())


def cli():
    from here_search.user import Permissive
    OneBoxConsole(Permissive(), term_keys=b'[]\\', item_keys='¡™£¢∞§¶•ªº'.encode()).run()


if __name__ == '__main__':
    cli()
