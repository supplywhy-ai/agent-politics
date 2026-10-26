"""Explicit state-change scope for the pinned AgentDojo workspace only.

These four implementations were inspected and do not mutate benchmark state.
This does NOT enforce confidentiality of reads or of the final assistant answer.
Unknown tools, including other read-looking names, still require model review.
"""
from study_prompts import digest

VERIFIED_READS = frozenset(('search_calendar_events','get_day_calendar_events',
                            'search_files_by_filename','list_files'))


def policy_receipt(packet):
    if packet['candidate']['function'] not in VERIFIED_READS:
        return None
    return {'function':packet['candidate']['function'],
            'candidate_hash':digest(packet['candidate']),
            'decision_source':'explicit_read_allowlist','decision':True}
