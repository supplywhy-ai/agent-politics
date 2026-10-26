"""Compare rendered prompts and semantic outputs of two saved episodes; no inference."""
import argparse
import copy
import hashlib
import json
from pathlib import Path
from mlx_lm.server import process_message_content
from mlx_lm.utils import load_tokenizer

def digest(x):return hashlib.sha256(json.dumps(x,sort_keys=True).encode()).hexdigest()

def semantic_response(r):
    c=r['response']['choices'][0]
    m=copy.deepcopy(c['message'])
    for t in m.get('tool_calls') or []:t.pop('id',None)
    return {'finish_reason':c['finish_reason'],'message':m}

def main():
    p=argparse.ArgumentParser();p.add_argument('--left',type=Path,required=True)
    p.add_argument('--right',type=Path,required=True);p.add_argument('--model-path',required=True)
    p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    tokenizer=load_tokenizer(a.model_path,tokenizer_config_extra={'trust_remote_code':False})
    def tokens(req):
        m=copy.deepcopy(req['messages']);assert not process_message_content(m)
        return tokenizer.apply_chat_template(m,tools=req.get('tools') or None,tokenize=True,add_generation_prompt=True)
    names=sorted({p.name for root in (a.left,a.right) for pattern in ('call-*.json','review-*.json') for p in root.glob(pattern)})
    rows=[]
    for name in names:
        l=a.left/name;r=a.right/name
        row={'record':name,'left_exists':l.exists(),'right_exists':r.exists()}
        if l.exists() and r.exists():
            left=json.loads(l.read_text());right=json.loads(r.read_text())
            lt=tokens(left['request']);rt=tokens(right['request'])
            row.update(rendered_prompt_equal=lt==rt,left_prompt_sha256=digest(lt),right_prompt_sha256=digest(rt),
                       left_prompt_tokens=len(lt),right_prompt_tokens=len(rt),
                       generation_settings_equal=all(left['request'].get(k)==right['request'].get(k) for k in ('model','temperature','seed','max_tokens')),
                       semantic_response_equal=semantic_response(left)==semantic_response(right))
        rows.append(row)
    result={'left':str(a.left),'right':str(a.right),'rows':rows,'model_calls':0,
            'scope':'Exact rendered token prompts and response messages excluding generated tool-call IDs. Observational comparison; does not identify a cause of differences.'}
    a.out.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))

if __name__=='__main__':main()
