import io, contextlib, tempfile, unittest
from pathlib import Path
from blackthorn.cli import main
from blackthorn.report import write_report
from blackthorn.hunt import namehunt
class VisualTests(unittest.TestCase):
 def test_original_art_embedded(self):
  with tempfile.TemporaryDirectory() as tmp:
   file=write_report(1,'Example Person',namehunt('Example Person'),tmp)
   data=file.read_text()
   self.assertIn('data:image/png;base64,',data)
   self.assertIn('img-src data:',data)
   self.assertIn('GLITCHBYTE PHANTOM LABS',data)
   self.assertNotIn('<script',data)
 def test_standalone_board(self):
  with tempfile.TemporaryDirectory() as tmp:
   with contextlib.redirect_stdout(io.StringIO()):
    self.assertEqual(main(['--board-art','--out',tmp]),0)
   self.assertEqual(len(list(Path(tmp).glob('*.html'))),1)
if __name__=='__main__':unittest.main()
