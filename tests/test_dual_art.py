import contextlib,io,unittest
from unittest.mock import patch
from pathlib import Path
from blackthorn import cli,report

class DualArtTests(unittest.TestCase):
    def test_distinct_source_files(self):
        self.assertNotEqual(cli.TOOL_ART,cli.BOARD_ART)
        self.assertTrue(cli.TOOL_ART.is_file())
        self.assertTrue(cli.BOARD_ART.is_file())
        self.assertEqual(report.ART,cli.BOARD_ART)
    def test_tool_cover_switch(self):
        with patch.object(cli,'show_picture',return_value=0) as viewer:
            self.assertEqual(cli.main(['--cover']),0)
            viewer.assert_called_once_with()
    def test_original_cover_switch(self):
        with patch.object(cli,'show_picture',return_value=0) as viewer:
            self.assertEqual(cli.main(['--original-cover']),0)
            viewer.assert_called_once_with(board=True)
    def test_no_art_bypasses_viewer(self):
        with patch.object(cli,'show_picture') as viewer,contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(cli.main(['--no-art','--menu']),0)
            viewer.assert_not_called()
if __name__=='__main__':unittest.main()
