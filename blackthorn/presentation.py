"""Shared output pipeline for all implemented BLACKTHORN modules."""
from .report import show_summary,write_report
from .dump import write_dump

def present(module,query,result,out="./BlackthornReports",verbose=False,dump=False,popup=False,html=False):
    show_summary(module,query,result,verbose=verbose)
    outputs=[]
    if dump:
        for path in write_dump(module,query,result,out):
            print("[DUMP] "+str(path))
            outputs.append(path)
    if popup or html:
        path=write_report(module,query,result,out,open_browser=popup)
        print("[BOARD] "+str(path))
        outputs.append(path)
    return outputs
