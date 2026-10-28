import unittest
from blackthorn.hunt import rank_candidates
class RankTests(unittest.TestCase):
 def test_relevance_is_not_identity(self):
  data=[{"title":"Rose Bowl","provider":"Wikipedia","url":"https://example.org/1","evidence":"x"},{"title":"Rose","provider":"OpenAlex","url":"https://example.org/2","evidence":"x"}]
  rows=rank_candidates("Rose",data)
  self.assertEqual(rows[0]["title"],"Rose")
  self.assertEqual(rows[0]["relevance_label"],"Exact display-title text")
  self.assertFalse(rows[0]["identity_verified"])
 def test_deduplicate(self):
  data=[{"title":"Jane","url":"https://example.org/1"}]*2
  self.assertEqual(len(rank_candidates("Jane",data)),1)
