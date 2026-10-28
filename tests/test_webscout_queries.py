import unittest
from urllib.parse import urlsplit, parse_qs
from blackthorn.cli import execute

class WebScoutTests(unittest.TestCase):
    def test_search_operator_preserved(self):
        q='site:facebook.com Jedisec'
        r=execute(9,q)
        self.assertEqual(r['query'],q)
        for url in r['sources'].values():
            self.assertEqual(parse_qs(urlsplit(url).query)['q'][0],q)
            self.assertIn('https',urlsplit(url).scheme)
    def test_no_fake_results(self):
        r=execute(9,'site:reddit.com Jedisec')
        self.assertEqual(r['retrieved_candidates'],[])
        self.assertIn('no search results fetched',r['status'])
    def test_quotes_preserved(self):
        r=execute(9,'"Jedisec.com"')
        self.assertEqual(parse_qs(urlsplit(r['sources']['Google web search']).query)['q'][0],'"Jedisec.com"')
    def test_empty_rejected(self):
        with self.assertRaises(ValueError): execute(9,'   ')
    def test_control_chars_rejected(self):
        with self.assertRaises(ValueError): execute(9,'test\nInjected')
