"""Shared sequential input+output token budget, not a FLOP or latency budget.

Reserve the entire requested output allowance before dispatch. Settle against
validated API usage; on an uncertain failure consume the reservation and close
the ledger. Never infer that a failed HTTP call consumed zero model resources.
"""
from copy import deepcopy
import hashlib
import json


class BudgetExhausted(RuntimeError):
    pass


class AccountingError(RuntimeError):
    pass


class TokenBudget:
    def __init__(self, limit, count_prompt):
        if type(limit) is not int or limit <= 0:
            raise ValueError('limit must be a positive integer')
        self.limit=limit
        self.count_prompt=count_prompt
        self.used=0
        self.closed=False
        self.events=[]

    def call(self, request, lane, dispatch):
        if self.closed:
            raise AccountingError('ledger is closed after an uncertain failure')
        if lane not in ('actor','reviewer'):
            raise ValueError('unknown inference lane')
        frozen=deepcopy(request)
        prompt=self.count_prompt(frozen)
        output=frozen.get('max_tokens')
        if type(prompt) is not int or prompt < 0 or type(output) is not int or output <= 0:
            raise ValueError('explicit valid prompt count and max_tokens required')
        reserve=prompt+output
        event={'lane':lane,'request_sha256':hashlib.sha256(
            json.dumps(frozen,sort_keys=True,separators=(',',':')).encode()).hexdigest(),
            'prompt_tokens':prompt,'output_allowance':output,'reservation':reserve,
            'used_before':self.used,'limit':self.limit}
        self.events.append(event)
        if self.used+reserve > self.limit:
            event.update(status='budget_denied',dispatched=False,used_after=self.used)
            raise BudgetExhausted('insufficient budget for prompt and full output allowance')
        self.used+=reserve
        event.update(status='reserved',dispatched=True)
        try:
            result=dispatch(frozen)
            usage=result['usage']
            p,c,t=(usage[k] for k in ('prompt_tokens','completion_tokens','total_tokens'))
            if not (all(type(v) is int for v in (p,c,t)) and p==prompt and
                    0<=c<=output and t==p+c):
                raise AccountingError('reported usage disagrees with reservation')
        except Exception as exc:
            self.closed=True
            event.update(status='uncertain_failure',error_type=type(exc).__name__,used_after=self.used)
            raise
        self.used-=reserve-t
        event.update(status='settled',actual_tokens=t,completion_tokens=c,used_after=self.used)
        return result

    def snapshot(self):
        return deepcopy({'limit':self.limit,'used':self.used,'closed':self.closed,'events':self.events,
                         'unit':'sum of rendered input and generated output tokens; not compute'})
