#!/usr/bin/env python3
"""Check project-context drift; never import/run the app, call Git, or use network.

check is read-only. record requires an explicit review acknowledgement and only
writes the review receipt and the marked section of AGENTS.md. Fingerprints are
not semantic reviews, UI tests, or generation-quality evidence. Python >= 3.10.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import sys
import tempfile
from datetime import datetime, timezone
from typing import Any

BEGIN = '<!-- TIMEFOREST_CONTEXT:BEGIN -->'
END = '<!-- TIMEFOREST_CONTEXT:END -->'
DEFAULT_CONFIG = 'docs/governance/context-check.json'
MAX_FILE = 2 * 1024 * 1024
MAX_TOTAL = 24 * 1024 * 1024
MAX_FILES = 1200


class GuardError(Exception):
    pass


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def stable_json(data: Any) -> bytes:
    return json.dumps(data, ensure_ascii=False, sort_keys=True,
                      separators=(',', ':')).encode('utf-8')


def valid_relative(value: str) -> str:
    if not isinstance(value, str) or not value or '\\' in value or ':' in value:
        raise GuardError(f'Use a nonempty relative POSIX path: {value!r}')
    p = PurePosixPath(value)
    if p.is_absolute() or '..' in p.parts or not p.parts or p.as_posix() != value:
        raise GuardError(f'Path escapes project scope: {value!r}')
    return value


def within(root: Path, value: str, must_exist: bool = True) -> Path:
    p = (root / valid_relative(value)).resolve()
    if not p.is_relative_to(root):
        raise GuardError(f'External symlink/path is not allowed: {value}')
    if must_exist and not p.is_file():
        raise GuardError(f'Required file missing: {value}')
    return p


def split_agents(text: str) -> tuple[str, str, str]:
    if text.count(BEGIN) != 1 or text.count(END) != 1:
        raise GuardError('AGENTS.md must have exactly one BEGIN/END managed pair.')
    a, b = text.index(BEGIN) + len(BEGIN), text.index(END)
    if b < a:
        raise GuardError('AGENTS.md managed markers are reversed.')
    return text[:a], text[a:b], text[b:]


def read_json(path: Path) -> dict[str, Any]:
    if path.stat().st_size > MAX_FILE:
        raise GuardError(f'Configuration/receipt too large: {path.name}')
    obj = json.loads(path.read_text(encoding='utf-8-sig'))
    if not isinstance(obj, dict):
        raise GuardError('Configuration/receipt must be a JSON object.')
    return obj


def path_list(value: Any, label: str, *, patterns: bool = False) -> list[str]:
    if not isinstance(value, list) or not all(isinstance(x, str) for x in value):
        raise GuardError(f'{label} must be a list of relative paths.')
    for item in value:
        valid_relative(item)
        if not patterns and any(c in item for c in '*?['):
            raise GuardError(f'{label} needs literal file paths: {item}')
        if patterns and any(c in PurePosixPath(item).parts[0] for c in '*?['):
            raise GuardError(f'Narrow {label} to a named source directory/file: {item}')
    return value


def validate_config(config: dict[str, Any]) -> None:
    if config.get('schema_version') != 1:
        raise GuardError('Unsupported configuration schema_version.')
    path_list([config.get('agents_file', 'AGENTS.md'), config['state_doc'],
               config['receipt_file']], 'Context paths')
    path_list(config.get('required_files', []), 'required_files')
    path_list(config.get('instruction_globs', []), 'instruction_globs', patterns=True)
    version = config['version_source']
    if not isinstance(version, dict):
        raise GuardError('version_source must be an object.')
    path_list([version['path']], 'version_source.path')
    if not all(isinstance(version.get(key), str) and version[key]
               for key in ('label', 'pattern')):
        raise GuardError('Version label and pattern must be nonempty strings.')
    if re.compile(version['pattern']).groups != 1:
        raise GuardError('Version pattern must have exactly one string capture.')
    if ('expected_matches' in version and
            (type(version['expected_matches']) is not int or version['expected_matches'] < 1)):
        raise GuardError('version_source.expected_matches must be a positive integer.')
    groups = config['groups']
    if not isinstance(groups, list) or not groups or not all(isinstance(g, dict) for g in groups):
        raise GuardError('groups must be a nonempty list of objects.')
    ids: set[str] = set()
    for group in groups:
        gid = group.get('id')
        if not isinstance(gid, str) or not gid or gid in ids:
            raise GuardError('Group IDs must be unique nonempty strings.')
        ids.add(gid)
        path_list(group['sources'], f'{gid}.sources', patterns=True)
        path_list(group['docs'], f'{gid}.docs')


def validate_receipt(receipt: dict[str, Any]) -> None:
    if receipt.get('schema_version') != 1:
        raise GuardError('Unsupported receipt schema_version; review before migration.')
    if not all(isinstance(receipt.get(key), str)
               for key in ('recorded_at', 'note', 'no_doc_change_reason', 'snapshot_id')):
        raise GuardError('Malformed receipt metadata; review before recording again.')
    snap = receipt.get('snapshot')
    if not isinstance(snap, dict) or not isinstance(snap.get('config_sha256'), str):
        raise GuardError('Malformed receipt snapshot.')
    version = snap.get('version')
    if not isinstance(version, dict) or not all(isinstance(version.get(k), str)
                                               for k in ('label', 'path', 'value')):
        raise GuardError('Malformed receipt version.')
    groups = snap.get('groups')
    if not isinstance(groups, dict) or not all(isinstance(g, dict) for g in groups.values()):
        raise GuardError('Malformed receipt groups.')
    maps = [snap.get('instructions'), snap.get('required_files')]
    for group in groups.values():
        maps.extend([group.get('sources'), group.get('docs')])
    if not all(isinstance(m, dict) and all(isinstance(k, str) and isinstance(v, str)
                                         for k, v in m.items()) for m in maps):
        raise GuardError('Malformed receipt file fingerprints.')


def take_snapshot(root: Path, config: dict[str, Any]) -> dict[str, Any]:
    validate_config(config)
    cache: dict[str, bytes] = {}
    total = 0

    def get(name: str) -> bytes:
        nonlocal total
        if name not in cache:
            path = within(root, name)
            size = path.stat().st_size
            if size > MAX_FILE or total + size > MAX_TOTAL or len(cache) >= MAX_FILES:
                raise GuardError('Scope is too large. Watch source/docs, not models or media.')
            data = path.read_bytes()
            if len(data) > MAX_FILE or total + len(data) > MAX_TOTAL:
                raise GuardError('File grew beyond scope limit while reading.')
            cache[name] = data
            total += len(data)
        return cache[name]

    def hashes(patterns: list[str]) -> dict[str, str]:
        names: set[str] = set()
        for pattern in patterns:
            valid_relative(pattern)
            # Check the literal prefix before glob traversal, not after reading it.
            parts = []
            for part in PurePosixPath(pattern).parts:
                if any(c in part for c in '*?['):
                    break
                parts.append(part)
            within(root, '/'.join(parts), must_exist=False)
            for path in root.glob(pattern):
                if path.is_file():
                    names.add(path.relative_to(root).as_posix())
                    if len(names) > MAX_FILES:
                        raise GuardError('Too many matches; narrow the source scope.')
        return {name: digest(get(name)) for name in sorted(names)}

    required = config.get('required_files', [])
    for name in required:
        get(name)
    version = config['version_source']
    version_text = get(version['path']).decode('utf-8-sig')
    matches = re.findall(version['pattern'], version_text)
    if not matches or any(not isinstance(x, str) for x in matches):
        raise GuardError('Version pattern must yield one string capture per match.')
    values = set(matches)
    if len(values) != 1:
        raise GuardError(f'Conflicting version evidence: {sorted(values)}')
    if 'expected_matches' in version and len(matches) != version['expected_matches']:
        raise GuardError('Version evidence count changed; review the static entry and pattern.')
    agents_name = config.get('agents_file', 'AGENTS.md')
    agents_text = get(agents_name).decode('utf-8')
    left, _, right = split_agents(agents_text)
    # Managed content is excluded to avoid a fingerprint self-reference cycle.
    instructions = hashes(config.get('instruction_globs', []))
    instructions[agents_name] = digest((left + '\n' + right).encode('utf-8'))
    groups: dict[str, Any] = {}
    for group in config['groups']:
        gid = group['id']
        if not isinstance(gid, str) or not gid or gid in groups:
            raise GuardError('Group IDs must be unique nonempty strings.')
        sources = hashes(group['sources'])
        if not sources:
            raise GuardError(f'No sources matched group {gid}; verify the current paths.')
        docs = {name: digest(get(name)) for name in group['docs']}
        if not docs:
            raise GuardError(f'Group {gid} must name its current documentation.')
        groups[gid] = {'sources': sources, 'docs': docs}
    if not groups:
        raise GuardError('No context groups configured.')
    required_names = set(required) | {config['state_doc'], version['path'], agents_name}
    required_hashes = {name: (instructions[agents_name] if name == agents_name else digest(get(name)))
                       for name in sorted(required_names)}
    return {
        'config_sha256': digest(stable_json(config)),
        'version': {'label': version['label'], 'path': version['path'],
                    'value': next(iter(values))},
        'instructions': instructions, 'required_files': required_hashes, 'groups': groups,
    }


def differences(old: dict[str, Any], new: dict[str, Any]) -> list[str]:
    notes: list[str] = []
    for key in ('config_sha256', 'version', 'instructions', 'required_files'):
        if old.get(key) != new.get(key):
            notes.append(f'changed: {key}')
    previous = old.get('groups', {})
    for gid in sorted(set(previous) | set(new['groups'])):
        before, after = previous.get(gid, {}), new['groups'].get(gid, {})
        for kind in ('sources', 'docs'):
            a, b = before.get(kind, {}), after.get(kind, {})
            changed = sorted(k for k in set(a) | set(b) if a.get(k) != b.get(k))
            if changed:
                preview = ', '.join(changed[:6])
                if len(changed) > 6:
                    preview += f' (+{len(changed)-6})'
                notes.append(f'{gid}/{kind}: {preview}')
    return notes


def managed_block(config: dict[str, Any], receipt: dict[str, Any]) -> str:
    snap = receipt['snapshot']
    v = snap['version']
    return (
        '\n'
        f"- {v['label']}：`{v['value']}`；证据：`{v['path']}`。\n"
        f"- 当前状态与交接：`{config['state_doc']}`。\n"
        f"- 最近内容复核（UTC）：{receipt['recorded_at']}。\n"
        f"- 本次交付/交接：{receipt['note']}\n"
        f"- 上下文快照：`{receipt['snapshot_id']}`；读取入口与相关规则仍以上文为准。\n"
        '- 此区仅记录接续上下文，不表示业务、部署或真实生成已通过验收。\n'
    )


def atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp: Path | None = None
    try:
        with tempfile.NamedTemporaryFile('wb', dir=path.parent,
                                         prefix='.context-', delete=False) as f:
            temp = Path(f.name)
            f.write(data)
        temp.replace(path)
    finally:
        if temp is not None and temp.exists():
            temp.unlink()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    for name in ('check', 'record'):
        p = sub.add_parser(name)
        p.add_argument('--root', default='.')
        p.add_argument('--config', default=DEFAULT_CONFIG)
        if name == 'record':
            p.add_argument('--reviewed', action='store_true', help='Explicit content-review acknowledgement')
            p.add_argument('--note', required=True, help='Short truthful delivery/handoff summary')
            p.add_argument('--no-doc-change-reason', default='', help='Why unchanged docs still describe changed code')
    args = parser.parse_args()
    try:
        root = Path(args.root).resolve(strict=True)
        config_path = within(root, args.config)
        config = read_json(config_path)
        validate_config(config)
        receipt_path = within(root, config['receipt_file'], must_exist=False)
        agents_path = within(root, config.get('agents_file', 'AGENTS.md'))
        # Only the receipt and the managed section may be written.
        if receipt_path in (agents_path, config_path, within(root, config['state_doc'])):
            raise GuardError('Receipt path must not overwrite configuration, AGENTS or state document.')
        snap = take_snapshot(root, config)
        tracked = set(snap['instructions']) | set(snap['required_files'])
        for group in snap['groups'].values():
            tracked.update(group['sources'])
            tracked.update(group['docs'])
        if any(receipt_path == within(root, name) for name in tracked):
            raise GuardError('Receipt must not overwrite a monitored source, instruction, or document.')
        previous = read_json(receipt_path) if receipt_path.is_file() else None
        if previous is not None:
            validate_receipt(previous)
        agents_bytes = agents_path.read_bytes()
        agents_text = agents_bytes.decode('utf-8')
        left, current_block, right = split_agents(agents_text)
        if args.command == 'check':
            if previous is None:
                print('REVIEW REQUIRED: no recorded context. Review current docs before record.')
                return 1
            notes = differences(previous['snapshot'], snap)
            if previous['snapshot_id'] != digest(stable_json(previous['snapshot']))[:16]:
                notes.append('receipt fingerprint mismatch')
            if current_block != managed_block(config, previous):
                notes.append('AGENTS current index differs from recorded review')
            if notes:
                print('REVIEW REQUIRED (not a ComfyUI or generation test):')
                for n in notes:
                    print(' -', n)
                return 1
            print('CONTEXT SNAPSHOT MATCHES. This is not semantic/UI/generation verification.')
            return 0
        note = args.note.strip()
        reason = args.no_doc_change_reason.strip()
        if not args.reviewed:
            raise GuardError('record requires --reviewed AFTER reviewing/updating current documentation.')
        if not note or len(note) > 240 or any(x in note for x in ('\n', '\r', '<!--', '-->')):
            raise GuardError('Provide a one-line truthful note of 1..240 characters.')
        if len(reason) > 1000 or any(x in reason for x in ('\n', '\r')):
            raise GuardError('Provide a one-line no-doc-change reason of at most 1000 characters.')
        if previous is not None:
            unchanged_docs = []
            for gid, group in snap['groups'].items():
                before = previous['snapshot']['groups'].get(gid)
                if before and before['sources'] != group['sources'] and before['docs'] == group['docs']:
                    unchanged_docs.append(gid)
            if unchanged_docs and not reason:
                print('REVIEW REQUIRED: source changed with unchanged docs in', ', '.join(unchanged_docs))
                print('Update the relevant docs, or provide a truthful --no-doc-change-reason after review.')
                return 1
        receipt = {
            'schema_version': 1,
            'recorded_at': datetime.now(timezone.utc).isoformat(timespec='seconds'),
            'note': note, 'no_doc_change_reason': reason,
            'snapshot_id': digest(stable_json(snap))[:16], 'snapshot': snap,
        }
        new_agents = left + managed_block(config, receipt) + right
        # Refuse to replace concurrent edits to AGENTS.
        if agents_path.read_bytes() != agents_bytes:
            raise GuardError('AGENTS changed during record; review and retry.')
        # A crash between these writes is detected by the next check.
        atomic_write(receipt_path, (json.dumps(receipt, ensure_ascii=False, indent=2) + '\n').encode('utf-8'))
        atomic_write(agents_path, new_agents.encode('utf-8'))
        print('Recorded explicit review and refreshed ONLY the managed AGENTS index.')
        print('No project state, rule text, runtime code, Git, network or generation was modified.')
        return 0
    except (GuardError, OSError, ValueError, KeyError, TypeError, re.error) as exc:
        print(f'CONFIGURATION/INPUT ERROR: {exc}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
