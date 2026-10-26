"""Repeat one frozen native request; record proposals only, never execute tools."""
import argparse
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import subprocess
import time
from openai import OpenAI

def digest(value):return hashlib.sha256(json.dumps(value,sort_keys=True).encode()).hexdigest()

def main():
    p=argparse.ArgumentParser();p.add_argument('--fixture',type=Path,required=True)
    p.add_argument('--server-pid',type=int,required=True);p.add_argument('--cache-size',type=int,choices=[0,10],required=True)
    p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    fixture=json.loads(a.fixture.read_text());request=fixture['request']
    assert digest(request)==fixture['request_sha256']
    command=subprocess.check_output(['ps','-p',str(a.server_pid),'-o','command='],text=True).strip()
    assert ' -m mlx_lm.server ' in command and ' --host 127.0.0.1 ' in command and ' --port 8791 ' in command
    assert request['model'] in command
    assert f'--prompt-cache-size {a.cache_size}' in command
    a.out.mkdir(parents=True,exist_ok=False)
    manifest={'status':'running','started_utc':datetime.now(timezone.utc).isoformat(),
              'fixture_sha256':hashlib.sha256(a.fixture.read_bytes()).hexdigest(),'fixture':fixture,
              'observed_server_command':command,'server_pid':a.server_pid,'cache_size':a.cache_size,
              'source_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              'scope':'Post-discovery repeated-request diagnostic. No tools executed; one fixed prompt, not independent tasks.'}
    def save(): (a.out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    save();(a.out/'runner-source.py').write_bytes(Path(__file__).read_bytes())
    client=OpenAI(base_url='http://127.0.0.1:8791/v1',api_key='local-no-secret',max_retries=0,timeout=180)
    rows=[]
    for i in range(fixture['repetitions_per_cache_mode']):
        started=time.perf_counter()
        response=client.chat.completions.create(**request).model_dump(mode='json')
        record={'request':request,'response':response,'elapsed_seconds':time.perf_counter()-started}
        (a.out/f'call-{i+1:02d}.json').write_text(json.dumps(record,indent=2)+'\n')
        message=json.loads(json.dumps(response['choices'][0]['message']))
        for t in message.get('tool_calls') or []:t.pop('id',None)
        rows.append({'index':i+1,'output_without_tool_ids_sha256':digest(message),
                     'finish_reason':response['choices'][0]['finish_reason'],
                     'proposed_tools':[t['function']['name'] for t in message.get('tool_calls') or []],
                     'usage':response['usage']})
        print(json.dumps(rows[-1]),flush=True)
    manifest.update(status='complete',finished_utc=datetime.now(timezone.utc).isoformat(),
                    calls=len(rows),unique_outputs=len({r['output_without_tool_ids_sha256'] for r in rows}),rows=rows)
    save()

if __name__=='__main__':main()
