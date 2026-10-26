"""Verify fixed-request diagnostic receipts; no tool execution or safety grading."""
import csv
from datetime import datetime
import hashlib
import json
from pathlib import Path
from count_native_tokens import count
from mlx_lm.utils import load_tokenizer

ROOT=Path(__file__).resolve().parents[1]
def digest(x):return hashlib.sha256(json.dumps(x,sort_keys=True).encode()).hexdigest()

def main():
    fixture_path=ROOT/'fixtures/repeatability-call-v1.json'
    fixture=json.loads(fixture_path.read_text())
    assert hashlib.sha256(Path(fixture['source_record']).read_bytes()).hexdigest()==fixture['source_record_sha256']
    assert digest(fixture['request'])==fixture['request_sha256']
    tokenizer=load_tokenizer(fixture['request']['model'],tokenizer_config_extra={'trust_remote_code':False})
    prompt_count=count(tokenizer,fixture['request'])
    rows=[];all_hashes=[];summary=[]
    previous_finish=None;server_pids=set()
    for mode in fixture['run_order']:
        folder=ROOT/'results'/f'repeatability-cache{mode}-v1'
        manifest=json.loads((folder/'manifest.json').read_text())
        assert manifest['status']=='complete' and manifest['fixture']==fixture
        assert manifest['server_pid'] not in server_pids
        server_pids.add(manifest['server_pid'])
        assert manifest['fixture_sha256']==hashlib.sha256(fixture_path.read_bytes()).hexdigest()
        assert hashlib.sha256((folder/'runner-source.py').read_bytes()).hexdigest()==manifest['source_sha256']
        assert datetime.fromisoformat(fixture['created_utc'])<datetime.fromisoformat(manifest['started_utc'])
        if previous_finish:assert previous_finish<datetime.fromisoformat(manifest['started_utc'])
        previous_finish=datetime.fromisoformat(manifest['finished_utc'])
        paths=sorted(folder.glob('call-*.json'))
        assert len(paths)==fixture['repetitions_per_cache_mode']==manifest['calls']
        hashes=[];mode_rows=[]
        for i,path in enumerate(paths,1):
            r=json.loads(path.read_text());assert r['request']==fixture['request']
            usage=r['response']['usage'];assert usage['prompt_tokens']==prompt_count
            assert usage['total_tokens']==usage['prompt_tokens']+usage['completion_tokens']
            choice=r['response']['choices'][0]
            assert choice['finish_reason']==manifest['rows'][i-1]['finish_reason']
            message=json.loads(json.dumps(choice['message']))
            for t in message.get('tool_calls') or []:t.pop('id',None)
            h=digest(message);hashes.append(h);all_hashes.append(h)
            assert manifest['rows'][i-1]['output_without_tool_ids_sha256']==h
            cached=usage['prompt_tokens_details']['cached_tokens']
            if mode==0 or i==1:assert cached==0
            tools=[t['function']['name'] for t in message.get('tool_calls') or []]
            assert tools==manifest['rows'][i-1]['proposed_tools']
            row={'cache_size':mode,'position':i,'cached_prompt_tokens':cached,
                 'prompt_tokens':prompt_count,'completion_tokens':usage['completion_tokens'],
                 'finish_reason':choice['finish_reason'],
                 'output_sha256':h,'proposed_tools':json.dumps(tools),'tools_executed':0}
            rows.append(row);mode_rows.append(row)
        assert len(set(hashes))==manifest['unique_outputs']
        summary.append({'cache_size':mode,'calls':len(paths),'unique_outputs':len(set(hashes)),
                        'calls_proposing_tools':sum(r['proposed_tools']!='[]' for r in mode_rows),
                        'cached_prompt_tokens_by_position':[r['cached_prompt_tokens'] for r in mode_rows]})
    with (ROOT/'results/repeatability-summary-v1.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    result={'receipt_checks_passed':True,'retokenized_prompt_count':prompt_count,'model_calls':len(rows),
            'verification_model_calls':0,'unique_outputs_across_modes':len(set(all_hashes)),
            'summary':summary,'scope':'One frozen request; exact message comparisons excluding tool-call IDs, not safety/utility evaluation or population inference.'}
    (ROOT/'results/repeatability-verification-v1.json').write_text(json.dumps(result,indent=2)+'\n')
    lines=[r'\begin{tabular}{lrrr}',r'\toprule',r'Cache capacity & Calls & Unique outputs & Tool proposals \\',r'\midrule']
    for s in summary:lines.append(f"{s['cache_size']} & {s['calls']} & {s['unique_outputs']} & {s['calls_proposing_tools']} "+r'\\')
    lines.extend([r'\bottomrule',r'\end{tabular}'])
    (ROOT/'manuscript/repeatability-table.tex').write_text('\n'.join(lines)+'\n')
    print(json.dumps(result,indent=2))

if __name__=='__main__':main()
