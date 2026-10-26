"""Native SDK adapter and persistent, inference-free tokenizer subprocess."""
import json
import subprocess
from pathlib import Path
from openai.types.chat import ChatCompletion
from token_budget import TokenBudget,BudgetExhausted,AccountingError

class TokenCounter:
    def __init__(self,python,model):
        self.process=subprocess.Popen([str(python),'-u',str(Path(__file__).with_name('count_native_tokens.py')),
            '--model-path',str(model)],stdin=subprocess.PIPE,stdout=subprocess.PIPE,text=True)
    def __call__(self,request):
        self.process.stdin.write(json.dumps(request)+'\n');self.process.stdin.flush()
        line=self.process.stdout.readline()
        if not line:raise AccountingError('tokenizer worker terminated')
        return json.loads(line)['prompt_tokens']
    def close(self):
        self.process.stdin.close()
        try:self.process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            self.process.terminate();self.process.wait(timeout=10)

class NativeBudget:
    def __init__(self,limit,counter,client,target):
        self.ledger=TokenBudget(limit,counter)
        self.client=client
        self.target=target
        self.terminal=None
    def call(self,request,lane):
        if self.terminal:
            raise self.terminal('episode stopped after first budget/accounting failure')
        record={'request':request,'lane':lane}
        index=len(self.ledger.events)+1
        def dispatch(req):
            raw=self.client.chat.completions.create(**req).model_dump(mode='json')
            record['response']=raw
            return raw
        try:
            return ChatCompletion.model_validate(self.ledger.call(request,lane,dispatch))
        except BudgetExhausted as exc:
            self.terminal=BudgetExhausted
            record['error_type']=type(exc).__name__
            raise
        except Exception as exc:
            self.terminal=AccountingError
            record['error_type']=type(exc).__name__
            raise
        finally:
            (self.target/f'budget-call-{index:02d}.json').write_text(json.dumps(record,indent=2)+'\n')
            (self.target/'budget.json').write_text(json.dumps(self.ledger.snapshot(),indent=2)+'\n')
