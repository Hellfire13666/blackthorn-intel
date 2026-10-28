import unittest
from blackthorn.cli import webscout_relevance
class Relevance(unittest.TestCase):
    def test_facebook_generic_excluded(self):
        rows=[{'title':'Facebook','url':'https://www.facebook.com/'},{'title':'JediSec | Facebook','url':'https://www.facebook.com/AnonzUnited/'}, {'title':'JediSec wiki','url':'https://en.wikipedia.org/wiki/JediSec'}]
        kept,excluded=webscout_relevance('site:facebook.com Jedisec',rows)
        self.assertEqual(len(kept),1);self.assertEqual(len(excluded),2)
    def test_plain_domain_hint(self):
        rows=[{'title':'Facebook login','url':'https://www.facebook.com/login'},{'title':'JediSec home','url':'https://www.facebook.com/AnonzUnited/'}]
        kept,_=webscout_relevance('facebook.com Jedisec',rows)
        self.assertEqual(len(kept),1)
    def test_no_identity_verification(self):
        row={'title':'JediSec','url':'https://www.facebook.com/JediSec','identity_verified':False}
        kept,_=webscout_relevance('Jedisec',[row]);self.assertFalse(kept[0]['identity_verified'])
