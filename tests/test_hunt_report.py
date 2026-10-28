import io, contextlib, tempfile, unittest
from blackthorn.hunt import namehunt
from blackthorn.cli import coordinates, main
from blackthorn.report import write_report
class HuntReportTests(unittest.TestCase):
 def test_name_pathways(self):
  r=namehunt('Example Person')
  self.assertGreaterEqual(sum(len(v) for v in r['categories'].values()),20)
  self.assertEqual(r['retrieved_candidates'],[])
 def test_escape(self):
  with tempfile.TemporaryDirectory() as d:
   r=namehunt('<script>alert(1)</script>')
   file=write_report(1,'<script>alert(1)</script>',r,d)
   page=file.read_text()
   self.assertNotIn('<script>alert(1)</script>',page)
   self.assertIn('&lt;script&gt;',page)
   self.assertEqual(file.stat().st_mode & 0o077,0)
 def test_cli_html(self):
  with tempfile.TemporaryDirectory() as d:
   with contextlib.redirect_stdout(io.StringIO()):
    self.assertEqual(main(['--module','1','--query','Example Person','--save-html','--out',d,'--no-art']),0)
   self.assertEqual(len(list(__import__('pathlib').Path(d).glob('*.html'))),1)
 def test_coordinate_guidance(self):
  with self.assertRaisesRegex(ValueError,'NETSPECTER'):coordinates('example.org')
if __name__=='__main__':unittest.main()
