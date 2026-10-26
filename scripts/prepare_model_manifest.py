"""Verify the pinned downloaded model and write a fresh local manifest."""
import hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
expected=json.loads((ROOT/'provenance/model-files.json').read_text())
model=ROOT/'work/models/qwen3-4b-instruct-2507-4bit'
for name,digest in expected['model_files_sha256'].items():
    path=model/name; h=hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda:stream.read(1024*1024),b''): h.update(block)
    if h.hexdigest()!=digest: raise ValueError(f'Model identity mismatch: {name}')
out=ROOT/'outputs/agent-politics-research/results/calibration-qwen-v1/manifest.json'
out.parent.mkdir(parents=True,exist_ok=True)
if out.exists():raise FileExistsError(out)
out.write_text(json.dumps(expected,indent=2)+'\n')
print('Pinned model verified; local manifest written.')
