import unittest
from unittest.mock import patch
from blackthorn.cli import webscout_links

class FakeResponse:
    def __init__(self, payload): self.payload=payload
    def __enter__(self): return self
    def __exit__(self, *args): pass
    def read(self, n): return self.payload

class TestWebscoutLive(unittest.TestCase):
    def test_offline_does_not_fetch(self):
        with patch('blackthorn.cli.urllib.request.urlopen') as fetch:
            r=webscout_links('site:facebook.com Jedisec')
        fetch.assert_not_called()
        self.assertEqual(r['retrieved_candidates'],[])
        self.assertIn('site%3Afacebook.com+Jedisec',r['sources']['Bing web search'])
    def test_live_candidates_dedup(self):
        xml=b'<rss><channel><item><title>Public page</title><link>https://example.org/a</link></item><item><title>Again</title><link>https://example.org/a</link></item></channel></rss>'
        with patch('blackthorn.cli.urllib.request.urlopen',return_value=FakeResponse(xml)):
            r=webscout_links('site:facebook.com Jedisec',live=True)
        self.assertEqual(len(r['retrieved_candidates']),0)
        self.assertEqual(r['excluded_irrelevant'],1)
        self.assertEqual(r['indexed_total'],1)
    def test_failure_visible(self):
        with patch('blackthorn.cli.urllib.request.urlopen',side_effect=OSError('offline')):
            r=webscout_links('test',live=True)
        self.assertTrue(r['provider_errors'])
        self.assertIn('unavailable',r['status'])
if __name__=='__main__':unittest.main()
