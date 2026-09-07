"""Isolated standard-library checks of the context tool, not of TimeForest.

Only temporary fixture data is mutated; no application modules are imported.
"""
from pathlib import Path
from tempfile import TemporaryDirectory
import json
import subprocess
import sys

SCRIPT = Path(__file__).with_name('context_guard.py')


def main() -> None:
    with TemporaryDirectory(prefix='timeforest-context-fixture-') as name:
        root = Path(name)
        for path, text in {
            'AGENTS.md': '\ufeff# Fixture\r\n<!-- TIMEFOREST_CONTEXT:BEGIN -->\r\nPending\r\n<!-- TIMEFOREST_CONTEXT:END -->\r\nUnmanaged rule.\r\n',
            'state.md': '# Current state\nFixture only.\n',
            'guide.md': '# Fixture guide\n',
            'code/module.py': 'VALUE = 1\n',
            'static/index.html': '<script src="app.js?v=1.0.0"></script>',
        }.items():
            p = root/path
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(text.encode('utf-8'))
        config = {
            'schema_version': 1, 'state_doc': 'state.md',
            'receipt_file': 'context-review.json',
            'version_source': {'label': 'Fixture entry version', 'path': 'static/index.html',
                               'pattern': r'app\.js\?v=([0-9.]+)'},
            'required_files': ['AGENTS.md', 'state.md', 'guide.md'],
            'instruction_globs': ['AGENTS.override.md', 'code/**/AGENTS.md',
                                 'code/**/AGENTS.override.md'],
            'groups': [{'id': 'fixture', 'sources': ['code/*.py', 'static/*.html'],
                        'docs': ['state.md', 'guide.md']}],
        }
        (root/'config.json').write_text(json.dumps(config), encoding='utf-8')
        calls = 0

        def call(command: str, expected: int, *extra: str) -> str:
            nonlocal calls
            before = {p.relative_to(root): p.read_bytes() for p in root.rglob('*') if p.is_file()}
            p = subprocess.run([sys.executable, str(SCRIPT), command, '--root', str(root),
                                '--config', 'config.json', *extra],
                               capture_output=True, encoding='utf-8', timeout=10)
            calls += 1
            assert p.returncode == expected, (p.returncode, expected, p.stdout, p.stderr)
            after = {p.relative_to(root): p.read_bytes() for p in root.rglob('*') if p.is_file()}
            if command == 'check' or expected != 0:
                assert after == before, 'Read-only/failed invocation changed fixture files'
            else:
                assert all(after.get(name) == content for name, content in before.items()
                           if name not in (Path('AGENTS.md'), Path('context-review.json')))
                for marker, take in ((b'<!-- TIMEFOREST_CONTEXT:BEGIN -->', 0),
                                     (b'<!-- TIMEFOREST_CONTEXT:END -->', 1)):
                    assert before[Path('AGENTS.md')].split(marker)[take] == after[Path('AGENTS.md')].split(marker)[take], 'Unmanaged AGENTS bytes changed'
            assert 'Traceback' not in p.stderr
            return p.stdout + p.stderr

        original = (root/'AGENTS.md').read_bytes()
        call('check', 1)  # no review yet; read-only
        assert (root/'AGENTS.md').read_bytes() == original
        call('record', 2, '--note', 'Not acknowledged')
        call('record', 0, '--reviewed', '--note', 'Fixture initial review, not application verification')
        call('check', 0)
        (root/'code/module.py').write_text('VALUE = 2\n', encoding='utf-8')
        call('check', 1)
        call('record', 1, '--reviewed', '--note', 'Missing document treatment')
        (root/'guide.md').write_text('# Fixture guide\nValue is two.\n', encoding='utf-8')
        call('record', 0, '--reviewed', '--note', 'Updated fixture docs')
        call('check', 0)
        (root/'code/new.py').write_text('NEW = True\n', encoding='utf-8')
        call('check', 1)
        call('record', 0, '--reviewed', '--note', 'Fixture internal addition',
             '--no-doc-change-reason', 'Fixture guide remains accurate')
        call('check', 0)
        (root/'code/new.py').unlink()
        call('check', 1)
        (root/'code/AGENTS.md').write_text('Nested fixture rule\n', encoding='utf-8')
        call('check', 1)
        call('record', 0, '--reviewed', '--note', 'Fixture deletion and nested rule reviewed',
             '--no-doc-change-reason', 'No fixture product behavior changed')
        call('check', 0)
        a = (root/'AGENTS.md').read_text(encoding='utf-8')
        (root/'AGENTS.md').write_text(a.replace('最近内容复核', 'Manual index edit'), encoding='utf-8')
        call('check', 1)
        call('record', 0, '--reviewed', '--note', 'Fixture index repaired')
        (root/'static/index.html').write_text('<script src="app.js?v=1.1.0"></script>', encoding='utf-8')
        call('check', 1)
        (root/'state.md').write_text('# Current fixture state\nEntry 1.1.0\n', encoding='utf-8')
        call('record', 0, '--reviewed', '--note', 'Fixture version updated')
        call('check', 0)
        assert '`1.1.0`' in (root/'AGENTS.md').read_text(encoding='utf-8')
        (root/'guide.md').unlink()
        call('check', 2)
        (root/'guide.md').write_text('# Fixture guide\nValue is two.\n', encoding='utf-8')
        call('check', 0)

        def set_config(value: dict) -> None:
            (root/'config.json').write_text(json.dumps(value), encoding='utf-8')

        # State and required files remain watched even outside all group docs.
        (root/'required-only.md').write_text('Required fixture context\n', encoding='utf-8')
        scoped = json.loads(json.dumps(config))
        scoped['groups'][0]['docs'] = ['guide.md']
        scoped['required_files'].append('required-only.md')
        set_config(scoped)
        call('record', 0, '--reviewed', '--note', 'Fixture scope reviewed')
        (root/'state.md').write_text('Changed fixture state\n', encoding='utf-8')
        call('check', 1)
        (root/'required-only.md').write_text('Changed required fixture context\n', encoding='utf-8')
        call('check', 1)
        call('record', 0, '--reviewed', '--note', 'Fixture references reviewed')

        for override in ('AGENTS.override.md', 'code/AGENTS.override.md'):
            (root/override).write_text('Fixture override only\n', encoding='utf-8')
            call('check', 1)
            (root/override).unlink()
        call('check', 0)

        valid_agents = (root/'AGENTS.md').read_bytes()
        for invalid_agents in (
            valid_agents.replace(b'<!-- TIMEFOREST_CONTEXT:END -->', b''),
            valid_agents + b'<!-- TIMEFOREST_CONTEXT:BEGIN -->',
            b'<!-- TIMEFOREST_CONTEXT:END --><!-- TIMEFOREST_CONTEXT:BEGIN -->',
        ):
            (root/'AGENTS.md').write_bytes(invalid_agents)
            call('check', 2)
        (root/'AGENTS.md').write_bytes(valid_agents)

        # Reject malformed config, escaping paths, broad patterns and empty groups.
        variants = []
        for key, value in (('required_files', 'guide.md'), ('groups', {}),
                           ('receipt_file', '../outside.json'), ('receipt_file', 'C:/outside.json')):
            variant = json.loads(json.dumps(scoped))
            variant[key] = value
            variants.append(variant)
        for source in ('**/*.py', 'code/no-match-*.py'):
            variant = json.loads(json.dumps(scoped))
            variant['groups'][0]['sources'] = [source]
            variants.append(variant)
        for receipt in ('AGENTS.md', 'config.json', 'state.md', 'guide.md',
                        'required-only.md', 'static/index.html', 'code/module.py'):
            variant = json.loads(json.dumps(scoped))
            variant['receipt_file'] = receipt
            variants.append(variant)
        for variant in variants:
            set_config(variant)
            call('record', 2, '--reviewed', '--note', 'Invalid fixture configuration')
        set_config(scoped)

        receipt_path = root/'context-review.json'
        valid_receipt = receipt_path.read_bytes()
        for invalid in ({}, {'schema_version': 1},
                        {**json.loads(valid_receipt), 'snapshot': []},
                        {**json.loads(valid_receipt), 'snapshot': {'config_sha256': 'fixture', 'version': []}}):
            receipt_path.write_text(json.dumps(invalid), encoding='utf-8')
            call('check', 2)
        damaged = json.loads(valid_receipt)
        damaged['snapshot_id'] = 'tampered-fingerprint'
        receipt_path.write_text(json.dumps(damaged), encoding='utf-8')
        call('check', 1)
        receipt_path.write_bytes(valid_receipt)

        # Both version sources must still exist and agree; these are file checks.
        versioned = json.loads(json.dumps(scoped))
        versioned['version_source']['pattern'] = r'(?:app\.js|style\.css)\?v=([0-9.]+)'
        versioned['version_source']['expected_matches'] = 2
        set_config(versioned)
        call('check', 2)  # only one matching version source
        (root/'static/index.html').write_text('app.js?v=1.1.0 style.css?v=1.2.0', encoding='utf-8')
        call('check', 2)
        (root/'static/index.html').write_text('app.js?v=1.1.0 style.css?v=1.1.0', encoding='utf-8')
        call('record', 0, '--reviewed', '--note', 'Fixture version evidence reviewed',
             '--no-doc-change-reason', 'Only fixture static version evidence expanded')
        call('check', 0)

        oversized = root/'code/oversized.py'
        oversized.write_bytes(b'#' * (2 * 1024 * 1024 + 1))
        call('check', 2)
        oversized.unlink()
        call('check', 0)

        # Some Windows installations prohibit symlink creation without elevation.
        symlink_checks = 0
        with TemporaryDirectory(prefix='timeforest-context-outside-') as outside_name:
            outside = Path(outside_name)
            (outside/'external.py').write_text('EXTERNAL = True\n', encoding='utf-8')
            link = root/'linked-code'
            try:
                link.symlink_to(outside, target_is_directory=True)
            except OSError:
                pass
            else:
                linked = json.loads(json.dumps(versioned))
                linked['groups'][0]['sources'] = ['linked-code/*.py']
                set_config(linked)
                call('check', 2)
                symlink_checks += 1
                link.unlink()
        print(f'Symlink escape checks: {symlink_checks} (0 means host creation permission unavailable).')
        print(f'PASS: {calls} isolated tool invocations; no application, Git, network, or generation executed.')


if __name__ == '__main__':
    main()
