import io
import unittest
from contextlib import redirect_stdout
from blackthorn.report import summary,show_summary

class LiveTerminalTest(unittest.TestCase):
    def setUp(self):
        self.data={"sources":{"Bing":"https://www.bing.com"},"live_requested":True,"status":"public search-index candidates retrieved; unverified","retrieved_candidates":[{"provider":"Bing RSS index","title":"Example candidate","url":"https://example.org/post","identity_verified":False}]}
    def test_summary_positive(self):
        h,n=summary(9,self.data)
        self.assertIn("1 public index candidates",h)
        self.assertNotIn("No results were retrieved",n)
    def test_numbered_terminal_results(self):
        out=io.StringIO()
        with redirect_stdout(out): show_summary(9,"site:facebook.com Jedisec",self.data,False)
        printed=out.getvalue()
        self.assertIn("[01] Example candidate",printed)
        self.assertIn("https://example.org/post",printed)
        self.assertIn("[TOTAL] 1 unverified",printed)
        self.assertNotIn("Full raw result",printed)
    def test_empty_live(self):
        d={**self.data,"retrieved_candidates":[]}
        h,n=summary(9,d)
        self.assertIn("0 indexed candidates",h)
        self.assertIn("no candidates",n)
    def test_link_only(self):
        d={**self.data,"live_requested":False,"retrieved_candidates":[]}
        h,n=summary(9,d)
        self.assertIn("No results fetched",n)
    def test_other_module_unaffected(self):
        out=io.StringIO()
        with redirect_stdout(out): show_summary(5,'example.org',{'public_addresses':['1.1.1.1']})
        self.assertIn('[DNS] 1.1.1.1',out.getvalue())
