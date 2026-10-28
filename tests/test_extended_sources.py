import unittest
from unittest.mock import patch
from blackthorn.hunt import live_public_search, namehunt
class ExtendedTests(unittest.TestCase):
 def test_new_sources_are_typed(self):
  def fake(url):
   if 'wikidata.org' in url:return {'search':[{'id':'Q123','label':'Sample Entity','description':'topic'}]}
   if 'openlibrary.org' in url:return {'docs':[{'key':'OL12A','name':'Sample Author'}]}
   if 'archive.org' in url:return {'response':{'docs':[{'identifier':'sample-item','title':'Sample item'}]}}
   return {}
  with patch('blackthorn.hunt._request_json',side_effect=fake):
   rows,errors,counts=live_public_search('Sample')
  self.assertFalse(errors)
  self.assertEqual({x['provider'] for x in rows},{'Wikidata','Open Library','Internet Archive'})
  self.assertTrue(all(x['record_type'] for x in rows))
 def test_namesake_not_verified(self):
  with patch('blackthorn.hunt.live_public_search',return_value=([{'provider':'Wikidata','title':'Rose','url':'https://www.wikidata.org/wiki/Q1','record_type':'knowledge entity','evidence':'topic'}],[],{'Wikidata':1})):
   data=namehunt('Rose',True)
  self.assertFalse(data['retrieved_candidates'][0]['identity_verified'])
 def test_pathways(self):
  data=namehunt('Example Person')
  self.assertGreaterEqual(sum(len(x) for x in data['categories'].values()),22)
if __name__=='__main__':unittest.main()
