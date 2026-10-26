"""Token-only worker/audit matching the pinned MLX server's text chat renderer."""
import argparse
import copy
import json
from pathlib import Path
import sys
from mlx_lm.server import process_message_content
from mlx_lm.utils import load_tokenizer


def count(tokenizer,request):
    messages=copy.deepcopy(request['messages'])
    assert not process_message_content(messages)
    prompt=tokenizer.apply_chat_template(messages,tools=request.get('tools') or None,
                                         tokenize=True,add_generation_prompt=True)
    return len(prompt)


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--model-path',required=True)
    p.add_argument('--audit-runs',nargs='*',type=Path)
    p.add_argument('--out',type=Path)
    args=p.parse_args()
    tokenizer=load_tokenizer(args.model_path,tokenizer_config_extra={'trust_remote_code':False})
    if args.audit_runs:
        rows=[]
        for run in args.audit_runs:
            budget_paths=sorted(run.glob('*/budget-call-*.json'))
            paths=budget_paths or sorted(list(run.glob('*/call-*.json'))+list(run.glob('*/review-*.json')))
            for path in paths:
                record=json.loads(path.read_text())
                if 'response' not in record and not path.name.startswith('budget-call-'):
                    continue
                computed=count(tokenizer,record['request'])
                if 'response' in record:
                    reported=record['response']['usage']['prompt_tokens']
                    source='api_usage'
                else:
                    index=int(path.stem.rsplit('-',1)[1])-1
                    reported=json.loads((path.parent/'budget.json').read_text())['events'][index]['prompt_tokens']
                    source='pre_dispatch_ledger'
                rows.append({'record':str(path),'computed_prompt_tokens':computed,
                             'reported_prompt_tokens':reported,'reference_source':source,'equal':computed==reported})
        result={'records':rows,'all_equal':all(r['equal'] for r in rows),'count':len(rows),
                'model_inference_calls':0,'scope':'Text chat, native tools, default template arguments; no vision or custom templates.'}
        if args.out:args.out.write_text(json.dumps(result,indent=2)+'\n')
        print(json.dumps({k:v for k,v in result.items() if k!='records'}))
        if not result['all_equal']:raise SystemExit(1)
    else:
        for line in sys.stdin:
            print(json.dumps({'prompt_tokens':count(tokenizer,json.loads(line))}),flush=True)


if __name__=='__main__':
    main()
