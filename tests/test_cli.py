import io, tempfile, unittest, contextlib
from pathlib import Path
from blackthorn.cli import main, execute, coordinates, image_info
class ConsoleTests(unittest.TestCase):
 def test_bare_launch_is_switchboard(self):
  buf=io.StringIO()
  with contextlib.redirect_stdout(buf): self.assertEqual(main([]),0)
  self.assertIn('BLACKTHORN // INTEL SWITCHBOARD',buf.getvalue())
 def test_public_search(self):
  r=execute(1,'Example Person')
  self.assertIn('google.com',r['categories']['GENERAL WEB'][0]['url'])
  self.assertIn('search links only',r['mode'])
 def test_geo(self):
  self.assertIn('openstreetmap.org',coordinates('40,-74')['map'])
  with self.assertRaises(ValueError): coordinates('96,0')
 def test_offline_dns(self):
  self.assertEqual(execute(5,'example.org')['status'],'network not used')
 def test_note_permissions(self):
  with tempfile.TemporaryDirectory() as t:
   r=execute(11,'Sample public research note',out=t)
   p=Path(r['saved'])
   self.assertTrue(p.is_file())
   self.assertEqual(p.stat().st_mode & 0o077,0)
 def test_planned_is_honest(self):
  self.assertEqual(execute(7,'00:11:22:33:44:55')['organizational_prefix'],'00:11:22')
if __name__=='__main__':unittest.main()
