import tempfile, unittest
from unittest.mock import patch
from pathlib import Path
from blackthorn.hunt import live_public_search
from blackthorn.dump import write_dump
class LiveDump(unittest.TestCase):
 def test_more_than_five(self):
  def fake(url):
   from urllib.parse import urlsplit,parse_qs
   if 'wikipedia.org' in url:
    x=parse_qs(urlsplit(url).query); offset=int(x.get('sroffset',[0])[0]);n=int(x.get('srlimit',[50])[0])
    return {'query':{'search':[{'title':'Demo '+str(i),'pageid':i+1} for i in range(offset,min(offset+n,100))]}}
   return {}
  with patch('blackthorn.hunt._request_json',side_effect=fake):
   records,errors,counts=live_public_search('Example',per_provider=100)
  self.assertEqual(counts['Wikipedia'],100)
 def test_exports(self):
  with tempfile.TemporaryDirectory() as folder:
   result={'retrieved_candidates':[{'provider':'Demo','title':str(i),'url':'https://example.org'} for i in range(20)]}
   files=write_dump(1,'Example',result,folder)
   self.assertEqual(len(files),3)
   self.assertEqual(len(files[1].read_text().splitlines()),20)
   self.assertTrue(all(f.stat().st_mode & 0o077==0 for f in files))
