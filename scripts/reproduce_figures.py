"""Regenerate main figures from published derived data; no inference."""
import subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
SRC=ROOT/'outputs/agent-politics-research/src'
for script,args in [('render_method_diagram.py',[]),('render_paper_budget.py',[]),('render_transfer_paired.py',['--repetition','1']),('render_transfer_repetitions.py',[])]:
    subprocess.run([sys.executable,str(SRC/script),*args],cwd=ROOT,check=True)
print('Regenerated four main figures without model inference.')
