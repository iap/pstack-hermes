"""Exercise delivery shell gates against real, isolated Git repositories."""

import os
import subprocess
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]


def git_env(**extra):
    # These fixtures use only local temporary repositories. Git hooks export
    # repository selectors; scrub all Git overrides for every subprocess,
    # including clone and the workflow shells that run Git internally.
    return {**{k: v for k, v in os.environ.items() if not k.startswith('GIT_')},
            'GIT_CONFIG_NOSYSTEM': '1', 'GIT_CONFIG_GLOBAL': os.devnull, **extra}


def git(repo, *args):
    return subprocess.check_output(['git', '-C', str(repo), *args],
                                   text=True, env=git_env()).strip()


@pytest.fixture(autouse=True)
def inherited_git_environment(tmp_path_factory, monkeypatch):
    """Run every delivery fixture as if invoked from a hook in another repo."""
    foreign = tmp_path_factory.mktemp('foreign-git')
    git(foreign, 'init', '-q')
    git(foreign, 'config', 'user.name', 'Original')
    git(foreign, 'config', 'user.email', 'original@example.invalid')
    (foreign / 'original').write_text('untouched')
    git(foreign, 'add', '.')
    git(foreign, 'commit', '-qm', 'original')

    def snapshot():
        return {str(p.relative_to(foreign)): p.read_bytes()
                for p in foreign.rglob('*') if p.is_file()}

    before = snapshot()
    for key, value in {
        'GIT_DIR': str(foreign / '.git'), 'GIT_WORK_TREE': str(foreign),
        'GIT_INDEX_FILE': str(foreign / '.git/index'),
        'GIT_COMMON_DIR': str(foreign / '.git'),
        'GIT_OBJECT_DIRECTORY': str(foreign / '.git/objects'),
        'GIT_CONFIG_COUNT': '1', 'GIT_CONFIG_KEY_0': 'core.bare', 'GIT_CONFIG_VALUE_0': 'true',
    }.items():
        monkeypatch.setenv(key, value)
    yield
    assert snapshot() == before, 'delivery fixture modified the invoking repository'


@pytest.mark.parametrize('change', ['none', 'timestamp', 'payload', 'source', 'converter', 'missing'])
def test_publish_ignores_only_timestamp(tmp_path, change):
    git(tmp_path, 'init', '-q')
    git(tmp_path, 'config', 'user.name', 'Fixture')
    git(tmp_path, 'config', 'user.email', 'fixture@example.invalid')
    provenance = tmp_path / '.build-provenance.txt'
    baseline = 'source_commit: abc123\nconverter: sha-a\nconverted_at: old\n'
    provenance.write_text(baseline)
    (tmp_path / 'plugin.json').write_text('payload')
    git(tmp_path, 'add', '.')
    git(tmp_path, 'commit', '-qm', 'baseline')
    if change == 'missing':
        provenance.unlink()
    elif change != 'none':
        updated = baseline.replace('converted_at: old', 'converted_at: new')
        if change == 'source':
            updated = updated.replace('abc123', 'def456')
        elif change == 'converter':
            updated = updated.replace('sha-a', 'sha-b')
        provenance.write_text(updated)
    if change == 'payload':
        (tmp_path / 'plugin.json').write_text('changed')
    git(tmp_path, 'add', '-A')
    workflow = yaml.safe_load((ROOT / '.github/workflows/publish-dist.yml').read_text())
    script = workflow['jobs']['publish']['steps'][-1]['run']
    condition = next(line.strip()[3:-6] for line in script.splitlines()
                     if line.strip().startswith('if git -C "$dist" diff'))
    result = subprocess.run(['bash', '-c', condition], env=git_env(dist=str(tmp_path)))
    assert result.returncode == (0 if change in ('none', 'timestamp') else 1)


@pytest.mark.parametrize(('payload_changed', 'provenance_change', 'expected'), [
    (False, 'timestamp', 0),
    (True, 'timestamp', 1),
    (False, 'source', 1),
    (False, 'converter', 1),
    (False, 'missing', 1),
    (False, 'no-timestamp', 1),
])
def test_release_requires_matching_payload(tmp_path, payload_changed, provenance_change, expected):
    remote = tmp_path / 'remote'
    remote.mkdir()
    git(remote, 'init', '-q', '-b', 'master')
    git(remote, 'config', 'user.name', 'Fixture')
    git(remote, 'config', 'user.email', 'fixture@example.invalid')
    (remote / 'pstack').mkdir()
    (remote / 'pstack/plugin.json').write_text('payload')
    (remote / 'pstack/.build-provenance.txt').write_text(
        'source_commit: abc123\nconverter: sha-a\nconverted_at: source\n'
    )
    git(remote, 'add', '.')
    git(remote, 'commit', '-qm', 'source')
    git(remote, 'checkout', '--orphan', 'dist')
    git(remote, 'rm', '-rf', '.')
    (remote / 'plugin.json').write_text('changed' if payload_changed else 'payload')
    if provenance_change == 'missing':
        pass
    elif provenance_change == 'no-timestamp':
        (remote / '.build-provenance.txt').write_text(
            'source_commit: abc123\nconverter: sha-a\n'
        )
    else:
        source = 'def456' if provenance_change == 'source' else 'abc123'
        converter = 'sha-b' if provenance_change == 'converter' else 'sha-a'
        (remote / '.build-provenance.txt').write_text(
            f'source_commit: {source}\nconverter: {converter}\nconverted_at: dist\n'
        )
    (remote / '.gitattributes').write_text('* text=auto eol=lf')
    git(remote, 'add', '.')
    git(remote, 'commit', '-qm', 'package')
    git(remote, 'checkout', 'master')
    checkout = tmp_path / 'checkout'
    subprocess.run(['git', 'clone', '-q', str(remote), str(checkout)], check=True, env=git_env())
    runtime = tmp_path / 'runtime'
    runtime.mkdir()
    env_file = tmp_path / 'env'
    workflow = yaml.safe_load((ROOT / '.github/workflows/release.yml').read_text())
    script = next(s['run'] for s in workflow['jobs']['build']['steps']
                  if s.get('name') == 'Verify release source and published package')
    result = subprocess.run(['bash', '-c', script], cwd=checkout,
                            env=git_env(RUNNER_TEMP=str(runtime), GITHUB_ENV=str(env_file)),
                            capture_output=True, text=True)
    assert result.returncode == expected, result.stderr
    if expected == 0:
        assert f'PACKAGE_SHA={git(remote, "rev-parse", "dist")}' in env_file.read_text()


@pytest.mark.parametrize(('changelog', 'expected'), [
    ('## [0.5.1] - 2026-10-31\n\n### Fixed\n- Release delivery.\n\n## [0.5.0]\nOld.\n', 0),
    ('## [Unreleased]\nFuture.\n\n## [0.5.0]\nOld.\n', 1),
    ('## [0.5.1]\n## [0.5.0]\nOld.\n', 1),
    ('## [0.5.1]\n\n  \n## [0.5.0]\nOld.\n', 1),
    ('## [0.5.10]\nAnother version.\n', 1),
])
def test_release_notes_require_versioned_changelog(tmp_path, changelog, expected):
    (tmp_path / 'CHANGELOG.md').write_text(changelog)
    workflow = yaml.safe_load((ROOT / '.github/workflows/release.yml').read_text())
    script = next(s['run'] for s in workflow['jobs']['build']['steps']
                  if s.get('name') == 'Extract release notes')
    package_sha, source_sha = 'a' * 40, 'b' * 40
    result = subprocess.run(['bash', '-c', script], cwd=tmp_path, capture_output=True, text=True,
                            env=git_env(TAG_NAME='v0.5.1', PACKAGE_SHA=package_sha,
                                        SOURCE_SHA=source_sha, GITHUB_REPOSITORY='iap/pstack-hermes'))
    assert result.returncode == expected, result.stderr
    if expected == 0:
        notes = (tmp_path / 'RELEASE_NOTES.md').read_text()
        assert '- Release delivery.' in notes and 'Old.' not in notes
        assert f'Source commit: {source_sha}' in notes
        assert f'Package commit: {package_sha}' in notes
        assert f'--ref {package_sha} --enable' in notes
        assert f'--ref {package_sha} --force --enable' in notes
