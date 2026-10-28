import contextlib, io, unittest
from unittest.mock import patch
from blackthorn.cli import main
class StartupTests(unittest.TestCase):
 def test_no_art_switch(self):
  with patch('blackthorn.cli.show_picture') as viewer, contextlib.redirect_stdout(io.StringIO()) as out:
   self.assertEqual(main(['--no-art']),0)
  viewer.assert_not_called()
  self.assertIn('INTEL SWITCHBOARD',out.getvalue())
 def test_gui_tty_opens_viewer(self):
  with patch('blackthorn.cli.sys.stdout') as screen, patch('blackthorn.cli.os.environ', {'DISPLAY':':1'}), patch('blackthorn.cli.show_picture') as viewer:
   screen.isatty.return_value=True
   self.assertEqual(main([]),0)
  viewer.assert_called_once_with()
 def test_command_does_not_open_viewer(self):
  with patch('blackthorn.cli.show_picture') as viewer, contextlib.redirect_stdout(io.StringIO()):
   self.assertEqual(main(['--module','1','--query','Example Person']),0)
  viewer.assert_not_called()
 def test_no_display_does_not_open_viewer(self):
  with patch('blackthorn.cli.os.environ',{}), patch('blackthorn.cli.show_picture') as viewer, contextlib.redirect_stdout(io.StringIO()):
   self.assertEqual(main([]),0)
  viewer.assert_not_called()
