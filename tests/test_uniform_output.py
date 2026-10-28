import io,tempfile,contextlib,unittest,csv,json
from pathlib import Path
from blackthorn.presentation import present
from blackthorn.cli import execute, main

class UniformOutput(unittest.TestCase):
 def test_all_existing_modules_export(self):
  with tempfile.TemporaryDirectory() as d:
   image=Path(d)/"test.png"; image.write_bytes(b"synthetic test")
   queries={1:"Example Person",2:"example_handle",3:"person@example.org",
            4:"+1 415 555 2671",5:"example.org",6:"40.7128,-74.0060",
            8:str(image),9:"example.org",11:"Sample note"}
   for module,query in queries.items():
    result=execute(module,query,out=d)
    with contextlib.redirect_stdout(io.StringIO()):
     paths=present(module,query,result,d,dump=True,html=True)
    self.assertEqual(len(paths),4)
    self.assertTrue(all(Path(p).exists() for p in paths))
 def test_quiet_default_avoids_candidates_flood(self):
  data={"retrieved_candidates":[{"provider":"Example", "title":f"Result {i}","url":"https://example.org"} for i in range(200)]}
  buf=io.StringIO()
  with contextlib.redirect_stdout(buf):present(1,"example",data)
  self.assertIn("200",buf.getvalue())
  self.assertNotIn("Result 199",buf.getvalue())
 def test_verbose_outputs_all_records(self):
  data={"retrieved_candidates":[{"provider":"Demo", "title":"Example output"}]}
  buf=io.StringIO()
  with contextlib.redirect_stdout(buf):present(1,"example",data,verbose=True)
  self.assertIn("Example output",buf.getvalue())
 def test_cli_switches(self):
  with tempfile.TemporaryDirectory() as d:
   b=io.StringIO()
   with contextlib.redirect_stdout(b):
    self.assertEqual(main(["--module","2","--query","example_handle","--dump","--save-html","--out",d,"--no-art"]),0)
   self.assertEqual(len(list(Path(d).glob('*.html'))),1)
   self.assertEqual(len(list(Path(d).glob('*.csv'))),1)
if __name__=="__main__": unittest.main()
