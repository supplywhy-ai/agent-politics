"""Record the isolated integration runtime and verify installed source identity."""
import argparse
import hashlib
import importlib.metadata
import json
from pathlib import Path
import platform
import subprocess
import sys
import agentdojo

PIN = '089ed468cf3ed0322acc66b0211f26d9d90dbf60'


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--repo',required=True,type=Path)
    p.add_argument('--out',required=True,type=Path)
    args = p.parse_args()
    revision = subprocess.check_output(['git','-C',str(args.repo),'rev-parse','HEAD'],text=True).strip()
    if revision != PIN:
        raise ValueError('Unreviewed AgentDojo revision')
    installed = Path(agentdojo.__file__).parent
    compared = {}
    for name in ('functions_runtime.py','types.py','agent_pipeline/tool_execution.py',
                 'task_suite/task_suite.py','default_suites/v1/workspace/injection_tasks.py'):
        a = (installed/name).read_bytes()
        b = (args.repo/'src/agentdojo'/name).read_bytes()
        if a != b:
            raise ValueError('Installed source mismatch: '+name)
        compared[name] = hashlib.sha256(a).hexdigest()
    packages = {d.metadata['Name']:d.version for d in importlib.metadata.distributions()}
    report = {'python':platform.python_version(),'platform':platform.platform(),
              'executable':sys.executable,'source_commit':revision,
              'installed_source_hashes_verified':compared,'packages':dict(sorted(packages.items())),
              'evidence_type':'environment_inventory_not_model_result'}
    args.out.mkdir(parents=True,exist_ok=True)
    (args.out/'environment.json').write_text(json.dumps(report,indent=2)+'\n')
    requirements = [f'{name}=={version}' for name,version in sorted(packages.items())
                    if name.lower() not in ('agentdojo','pip','setuptools')]
    requirements.append('agentdojo @ git+https://github.com/ethz-spylab/agentdojo.git@'+revision)
    (args.out/'requirements-lock.txt').write_text('\n'.join(requirements)+'\n')
    print(json.dumps({'verified_source_files':len(compared),'packages':len(packages),'python':report['python']}))


if __name__ == '__main__':
    main()
