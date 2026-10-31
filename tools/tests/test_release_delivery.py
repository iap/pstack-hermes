"""Exercise delivery shell gates against real, isolated Git repositories."""

import os
import subprocess
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]


def git(repo, *args):
    return subprocess.check_output(['git', '-C', str(repo), *args], text=True).strip()


@pytest.mark.parametrize('payload_changed', [False, True])
def test_publish_ignores_only_provenance(tmp_path, payload_changed):
    git(tmp_path, 'init', '-q')
    git(tmp_path, 'config', 'user.name', 'Fixture')
    git(tmp_path, 'config', 'user.email', 'fixture@example.invalid')
    (tmp_path / '.build-provenance.txt').write_text('old')
    (tmp_path / 'plugin.json').write_text('payload')
    git(tmp_path, 'add', '.')
    git(tmp_path, 'commit', '-qm', 'baseline')
    (tmp_path / '.build-provenance.txt').write_text('new')
    if payload_changed:
        (tmp_path / 'plugin.json').write_text('changed')
    git(tmp_path, 'add', '.')
    workflow = yaml.safe_load((ROOT / '.github/workflows/publish-dist.yml').read_text())
    script = workflow['jobs']['publish']['steps'][-1]['run']
    condition = next(line.strip()[3:-6] for line in script.splitlines()
                     if line.strip().startswith('if git -C "$dist" diff'))
    result = subprocess.run(['bash', '-c', condition], env={**os.environ, 'dist': str(tmp_path)})
    assert result.returncode == (1 if payload_changed else 0)


@pytest.mark.parametrize('payload_changed', [False, True])
def test_release_requires_matching_payload(tmp_path, payload_changed):
    remote = tmp_path / 'remote'
    remote.mkdir()
    git(remote, 'init', '-q', '-b', 'master')
    git(remote, 'config', 'user.name', 'Fixture')
    git(remote, 'config', 'user.email', 'fixture@example.invalid')
    (remote / 'pstack').mkdir()
    (remote / 'pstack/plugin.json').write_text('payload')
    (remote / 'pstack/.build-provenance.txt').write_text('source-stamp')
    git(remote, 'add', '.')
    git(remote, 'commit', '-qm', 'source')
    git(remote, 'checkout', '--orphan', 'dist')
    git(remote, 'rm', '-rf', '.')
    (remote / 'plugin.json').write_text('changed' if payload_changed else 'payload')
    (remote / '.build-provenance.txt').write_text('different-stamp')
    (remote / '.gitattributes').write_text('* text=auto eol=lf')
    git(remote, 'add', '.')
    git(remote, 'commit', '-qm', 'package')
    git(remote, 'checkout', 'master')
    checkout = tmp_path / 'checkout'
    subprocess.run(['git', 'clone', '-q', str(remote), str(checkout)], check=True)
    runtime = tmp_path / 'runtime'
    runtime.mkdir()
    env_file = tmp_path / 'env'
    workflow = yaml.safe_load((ROOT / '.github/workflows/release.yml').read_text())
    script = next(s['run'] for s in workflow['jobs']['build']['steps']
                  if s.get('name') == 'Verify release source and published package')
    result = subprocess.run(['bash', '-c', script], cwd=checkout,
                            env={**os.environ, 'RUNNER_TEMP': str(runtime),
                                 'GITHUB_ENV': str(env_file)}, capture_output=True, text=True)
    assert result.returncode == (1 if payload_changed else 0), result.stderr
    if not payload_changed:
        assert f'PACKAGE_SHA={git(remote, "rev-parse", "dist")}' in env_file.read_text()
