# Reproduction

## Derived results and manuscript

The README quick start reproduces figures from saved CSV values. This is different from re-running inference or verifying raw trajectories. Compile `outputs/agent-politics-research/manuscript/main.tex` with Tectonic or a standard LaTeX distribution supporting the listed packages.

The source layout intentionally preserves the experiment runner's `outputs/agent-politics-research` and `work` directories. Run commands from the repository root. Included CSVs are published results; fresh runner outputs use separate directories and do not replace those tables automatically.

## New local inference (Apple Silicon)

The experiment used Python 3.12, MLX-LM 0.32.2, MLX 0.32.4, MLX-Metal 0.32.4 and Transformers 5.20.2. A machine capable of running the four-bit model is required. There are no paid API calls in these commands.

```sh
mkdir -p work/models
python3.12 -m venv work/agentdojo-venv
python3.12 -m venv work/mlx-venv
work/agentdojo-venv/bin/pip install 'agentdojo @ git+https://github.com/ethz-spylab/agentdojo.git@089ed468cf3ed0322acc66b0211f26d9d90dbf60'
work/mlx-venv/bin/pip install 'mlx-lm==0.32.2' 'mlx==0.32.4' 'mlx-metal==0.32.4' 'transformers==5.20.2' 'huggingface-hub==2.3.0'
work/mlx-venv/bin/hf download mlx-community/Qwen3-4B-Instruct-2507-4bit --revision 50d427756c6b1b2fe0c0a10f67fbda1fc8e82c1b --local-dir work/models/qwen3-4b-instruct-2507-4bit
python3.12 scripts/prepare_model_manifest.py
```

Start the loopback-only server in one terminal:

```sh
PYTHONHASHSEED=20261025 HF_HUB_OFFLINE=1 work/mlx-venv/bin/python -m mlx_lm.server --model "$PWD/work/models/qwen3-4b-instruct-2507-4bit" --host 127.0.0.1 --port 8791 --max-tokens 512 --temp 0 --prompt-cache-size 10
```

After its health endpoint responds, run one clean task in another terminal:

```sh
curl --fail http://127.0.0.1:8791/health
PYTHONHASHSEED=20261025 work/agentdojo-venv/bin/python outputs/agent-politics-research/src/agentdojo_local_live.py --model-path "$PWD/work/models/qwen3-4b-instruct-2507-4bit" --model-manifest outputs/agent-politics-research/results/calibration-qwen-v1/manifest.json --token-counter-python work/mlx-venv/bin/python --token-budget 64000 --tasks user_task_1 --review minimized --read-policy allow_verified_reads --out work/example-clean-run
PYTHONHASHSEED=20261025 work/agentdojo-venv/bin/python outputs/agent-politics-research/src/verify_agentdojo_live.py --runs work/example-clean-run
```

For a fixed three-payload attack run, replace `--tasks user_task_1` with `--attack-fixture outputs/agent-politics-research/fixtures/task-transfer-v1/user_task_1.json` and choose a new output directory. All tool actions occur inside AgentDojo's fictional in-memory workspace.

`run_transfer_batch.py` can run complete cohorts after the model manifest is prepared. It requires previous cohorts, refuses overwriting results, and freezes a new execution specification. The provided `execution-spec.reference.json` records the original source hashes; fixture paths have been made relative in this public release. Treat fresh runs as new evidence, not bitwise reproduction guarantees.

## Verification scope

Recorded-decision replay checks native tool state, messages, scores and budget receipts. It does not establish semantic correctness or deterministic model outputs. Exposure audits match normalized exact payload text. Effect audits cover exact-goal successful email sends, not every unauthorized action. The main study uses a shared token cap, not equal actual computation, latency or cost.

The integration suite includes archive-dependent tests. Run it only with the corresponding full study archive available. Public core tests and figure reproduction are independently runnable from this checkout.
