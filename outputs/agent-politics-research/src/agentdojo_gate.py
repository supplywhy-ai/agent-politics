"""Pre-action gate for the pinned AgentDojo ToolsExecutor.

Optional dependency: AgentDojo from inspected commit 089ed468cf3ed0322acc66b0211f26d9d90dbf60.
The reviewer receives immutable JSON, never the live environment or runtime.
This enforces the boundary only for calls through this executor; Python-level
access to the runtime or a malicious host is outside the threat model.
"""
import json
from agentdojo.agent_pipeline.tool_execution import ToolsExecutor
from agentdojo.functions_runtime import EmptyEnv, FunctionCall
from study_prompts import digest


def serializable(obj):
    if hasattr(obj,'model_dump'):
        return obj.model_dump()
    raise TypeError(f'Cannot serialize {type(obj).__name__}')


def contains_nested_call(value):
    if isinstance(value,FunctionCall):
        return True
    if isinstance(value,dict):
        return any(contains_nested_call(v) for v in value.values())
    if isinstance(value,(list,tuple)):
        return any(contains_nested_call(v) for v in value)
    return False


class GatedToolsExecutor(ToolsExecutor):
    def __init__(self, reviewer):
        super().__init__()
        self.reviewer = reviewer

    def query(self, query, runtime, env=None, messages=None, extra_args=None):
        env = EmptyEnv() if env is None else env
        messages = [] if messages is None else messages
        extras = dict(extra_args or {})
        audit = list(extras.get('sidecar_audit',[]))
        # Freeze input before any model-backed review; do not expose env/labels.
        history = json.loads(json.dumps(messages,default=serializable))
        reviewer = self.reviewer

        class GateRuntime:
            functions = runtime.functions

            def run_function(self, live_env, function, args, *pos, **kwargs):
                if contains_nested_call(args):
                    audit.append({'function':function,'decision':'unsupported_nested_call'})
                    return None, 'Security review: unsupported_nested_call'
                candidate_json = json.dumps({'function':function,'args':args},
                                            default=serializable,sort_keys=True)
                candidate = json.loads(candidate_json)
                packet = {'trusted_request':query,'candidate':candidate,
                          'recorded_history':history}
                packet_json = json.dumps(packet,sort_keys=True)
                try:
                    decision = reviewer(packet_json)
                    status = 'allowed' if decision is True else 'blocked' if decision is False else 'invalid_review'
                except Exception:
                    decision, status = None, 'review_unavailable'
                audit.append({'candidate_hash':digest(json.loads(candidate_json)),
                              'review_packet_hash':digest(json.loads(packet_json)),
                              'function':function,'decision':status})
                if decision is not True:
                    return None, 'Security review: '+status
                # Execute the frozen candidate, not any mutable review object.
                approved = json.loads(candidate_json)
                return runtime.run_function(live_env,approved['function'],approved['args'],*pos,**kwargs)

        _, _, updated_env, updated_messages, _ = super().query(query,GateRuntime(),env,messages,extras)
        extras['sidecar_audit'] = audit
        return query, runtime, updated_env, updated_messages, extras
