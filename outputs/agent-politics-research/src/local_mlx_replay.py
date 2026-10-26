"""Real local inference for the paired replay pilot, not live agent trajectories.

Use a separately downloaded, revision-pinned MLX snapshot. No external actions
or remote inference are performed. Each call starts with a fresh prompt cache.
"""
import argparse
from datetime import datetime, timezone
import hashlib
from importlib.metadata import distributions
import json
from pathlib import Path
import platform
import time

from replay_pipeline import prepare, prepare_reviews, read_cases, score
from study_prompts import digest


def save(path, obj):
    temp = path.with_suffix(path.suffix + '.tmp')
    temp.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + '\n')
    temp.replace(path)


def file_hash(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--model-path', required=True, type=Path)
    parser.add_argument('--model-repo', required=True)
    parser.add_argument('--revision', required=True)
    parser.add_argument('--cases', required=True, type=Path)
    parser.add_argument('--out', required=True, type=Path)
    parser.add_argument('--max-tokens', type=int, default=128)
    parser.add_argument('--seed', type=int, default=20261025)
    parser.add_argument('--include-probes', action='store_true')
    parser.add_argument('--requests', type=Path, help='Run a frozen request list instead of candidate replay')
    args = parser.parse_args()
    cases = read_cases(args.cases)
    frozen_requests = json.loads(args.requests.read_text()) if args.requests else None
    if frozen_requests is not None and len({r['request_id'] for r in frozen_requests}) != len(frozen_requests):
        raise ValueError('Frozen request IDs must be unique')
    args.out.mkdir(parents=True, exist_ok=False)
    import mlx.core as mx
    from mlx_lm import load, stream_generate
    from mlx_lm.sample_utils import make_sampler

    model_id = args.model_repo + '@' + args.revision
    manifest = {
        'status': 'loading', 'started_utc': datetime.now(timezone.utc).isoformat(),
        'model_id': model_id, 'model_path': str(args.model_path.resolve()),
        'revision_provenance': 'CLI supplied; retain pinned snapshot download record',
        'model_files_sha256': {str(p.relative_to(args.model_path)): file_hash(p)
                               for p in sorted(args.model_path.rglob('*'))
                               if p.is_file() and '.cache' not in p.parts},
        'cases_sha256': file_hash(args.cases), 'cases': cases,
        'source_sha256': {p.name: file_hash(p) for p in Path(__file__).parent.glob('*.py')},
        'python': platform.python_version(), 'platform': platform.platform(),
        'packages': dict(sorted((d.metadata['Name'], d.version) for d in distributions())),
        'settings': {'temperature': 0, 'max_tokens': args.max_tokens, 'seed': args.seed,
                     'fresh_prompt_cache_each_call': True, 'trust_remote_code': False,
                     'chat_template': 'apply_chat_template tokenize=True add_generation_prompt=True'},
        'purpose': 'development instrumentation; paired candidate replay, not held-out evaluation',
        'paid_api_calls': 0, 'records_completed': 0,
        'request_file_sha256': file_hash(args.requests) if args.requests else None,
        'experiment_kind': 'frozen_request_diagnostic' if args.requests else 'candidate_replay',
    }
    save(args.out / 'manifest.json', manifest)
    calls = []
    try:
        start = time.perf_counter()
        model, tokenizer = load(str(args.model_path), trust_remote_code=False)
        manifest['load_seconds'] = time.perf_counter() - start
        manifest['status'] = 'running'
        save(args.out / 'manifest.json', manifest)

        def run(requests, name):
            save(args.out / (name + '-requests.json'), requests)
            records = []
            save(args.out / (name + '.json'), records)
            for req in requests:
                mx.random.seed(args.seed)
                prompt = tokenizer.apply_chat_template(req['messages'], tokenize=True,
                                                       add_generation_prompt=True)
                start = time.perf_counter()
                pieces = []
                last = None
                for response in stream_generate(model, tokenizer, prompt=prompt,
                                                max_tokens=args.max_tokens,
                                                sampler=make_sampler(temp=0)):
                    pieces.append(response.text)
                    last = response
                if last is None:
                    raise RuntimeError('Model returned no generation response')
                elapsed = time.perf_counter() - start
                record = {'request_id': req['request_id'], 'origin': 'model_recording',
                          'model_id': model_id, 'text': ''.join(pieces)}
                receipt = {'request_id': req['request_id'], 'mode': req['mode'],
                           'stage': name, 'call_index': len(calls) + 1,
                           'prompt_token_ids_sha256': digest(prompt),
                           'prompt_tokens': last.prompt_tokens,
                           'generation_tokens': last.generation_tokens,
                           'elapsed_seconds': elapsed, 'finish_reason': last.finish_reason,
                           'peak_memory_gb': last.peak_memory, 'response_sha256': digest(record)}
                records.append(record)
                calls.append(receipt)
                save(args.out / (name + '.json'), records)
                save(args.out / 'calls.json', calls)
                manifest['records_completed'] = len(calls)
                save(args.out / 'manifest.json', manifest)
                print(json.dumps({'call': len(calls), 'case': req['case_id'],
                                  'hardened': req['executor_hardened'], 'mode': req['mode'],
                                  'text': record['text'], 'seconds': round(elapsed, 3)}), flush=True)
            return records

        if frozen_requests is not None:
            run(frozen_requests, 'diagnostic')
        else:
            generations = run(prepare(cases), 'generations')
            reviews = run(prepare_reviews(cases, generations), 'reviews')
            save(args.out / 'score.json', score(cases, generations, reviews))
            if args.include_probes:
                from reviewer_probes import prepare_probes, score_probes
                probe_requests = prepare_probes(cases)
                probes = run(probe_requests, 'probes')
                save(args.out / 'probe-score.json', score_probes(probe_requests, probes))
        manifest.update(status='complete', finished_utc=datetime.now(timezone.utc).isoformat(),
                        total_prompt_tokens=sum(c['prompt_tokens'] for c in calls),
                        total_generation_tokens=sum(c['generation_tokens'] for c in calls),
                        inference_seconds=sum(c['elapsed_seconds'] for c in calls))
        save(args.out / 'manifest.json', manifest)
    except BaseException as exc:
        manifest.update(status='failed', error_type=type(exc).__name__, error=str(exc))
        save(args.out / 'manifest.json', manifest)
        raise


if __name__ == '__main__':
    main()
