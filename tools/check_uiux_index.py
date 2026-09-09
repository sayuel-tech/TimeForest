"""Read-only UI/UX index checks; --refresh writes only mechanical maps and asset inventory.

No application imports, production data, network calls, or test execution.
"""
import argparse
import hashlib
import json
import re
from pathlib import Path
from urllib.parse import unquote


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def encoded(value):
    return json.dumps(value, ensure_ascii=False, indent=2) + '\n'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--index-root', type=Path, help='Optional staging docs/uiux directory')
    parser.add_argument('--refresh', action='store_true')
    parser.add_argument('--topic', help='Topic ID or exact keyword; prints only the selected catalog entry')
    parser.add_argument('--file', help='Repository-relative source path; prints ownership and direct importers')
    args = parser.parse_args()
    root = args.root.resolve()
    index = (args.index_root or root / 'docs/uiux').resolve()
    catalog = read_json(index / 'catalog.json')
    topics = catalog['topics']
    if args.topic:
        selected = [t for t in topics if args.topic in [t['id'], t['title'], *t['aliases']]]
        print(encoded(selected).rstrip())
        return 0 if selected else 1
    errors = []
    def safe_relative(value):
        path = (root / value).resolve()
        if not path.is_relative_to(root):
            raise ValueError('Outside repository: ' + value)
        return path
    js_paths = sorted((root / 'static/studio').rglob('*.js'))
    records = {}
    importers = {}
    for path in js_paths:
        name = path.relative_to(root).as_posix()
        content = path.read_text(encoding='utf-8-sig')
        imports = []
        for match in re.finditer(r'''(?:\bfrom\s*|\bimport\s*\(\s*|\bimport\s*)['"](\.[^'"]+)['"]''', content):
            dep = (path.parent / match[1]).resolve()
            if dep.is_relative_to(root):
                rel = dep.relative_to(root).as_posix()
                imports.append(rel)
                importers.setdefault(rel, set()).add(name)
                if not dep.is_file():
                    errors.append('Missing static import: ' + name + ' -> ' + rel)
        symbols = [{'name': m[1], 'line': content[:m.start()].count('\n') + 1}
                   for m in re.finditer(r'export\s+(?:async\s+)?(?:function|class|const|let)\s+(\w+)', content)]
        records[name] = {'sha256': digest(path), 'exports': symbols, 'imports': sorted(set(imports))}
    covered = set()
    generated = {}
    ids = set()
    for topic in topics:
        ident = topic['id']
        if not re.fullmatch(r'[a-z_]+', ident) or ident in ids:
            raise ValueError('Invalid/duplicate topic ID: ' + ident)
        ids.add(ident)
        if not (index / topic['doc']).is_file():
            errors.append('Missing topic document: ' + topic['doc'])
        source_paths = set()
        for pattern in topic['source_patterns']:
            safe_relative(pattern)
            matched = {p.relative_to(root).as_posix() for p in root.glob(pattern) if p.is_file()}
            if not matched:
                errors.append('Empty source pattern: ' + pattern)
            source_paths.update(matched)
        covered.update(source_paths)
        if sorted(source_paths) != sorted(topic['entrypoints']):
            errors.append('Catalog entrypoints changed; review/update topic: ' + ident)
        for p in topic['tests'] + topic['references']:
            if not safe_relative(p).is_file():
                errors.append('Missing referenced file: ' + p)
        generated['maps/' + ident + '.json'] = {
            'schema_version': 1,
            'topic': ident,
            'evidence': 'Mechanical current-source map; not UI acceptance or a match to historical screenshots.',
            'sources': {p: {**records.get(p, {'sha256': digest(root / p)}),
                            'imported_by': sorted(importers.get(p, set()))}
                        for p in sorted(source_paths)}
        }
    wanted = {p.relative_to(root).as_posix() for p in js_paths}
    wanted.update(p.relative_to(root).as_posix() for p in (root / 'static/studio/styles').glob('*.css'))
    wanted.update(['static/index.html', 'static/studio/style.css', 'static/styles/tokens.css'])
    errors.extend('Unmapped frontend file: ' + p for p in sorted(wanted - covered))
    registry = (root / 'static/studio/app/mode-registry.js').read_text(encoding='utf-8-sig')
    modes = set(re.findall(r'''\bid\s*:\s*['"]([^'"]+)['"]''', registry))
    errors.extend('Unmapped registered mode: ' + p for p in sorted(modes - ids))
    texts = {p.relative_to(root).as_posix(): p.read_text(encoding='utf-8-sig')
             for p in sorted({root / p for p in covered}) if p.suffix in ('.js', '.css', '.html')}
    assets = []
    for path in sorted((root / 'static/assets').rglob('*')):
        if path.suffix.lower() not in ('.webp', '.svg', '.png', '.jpg', '.jpeg') or not path.is_file():
            continue
        rel = path.relative_to(root).as_posix()
        assets.append({'path': rel, 'bytes': path.stat().st_size, 'sha256': digest(path),
                       'referenced_by_text': [p for p, content in texts.items() if path.name in content],
                       'preservation': 'Preserve first; file existence does not imply individual user approval.'})
    generated['visuals/assets.json'] = {'schema_version': 1,
        'reference_method': 'Literal filename matches in indexed frontend; dynamic references may be missing. Empty references do not authorize deletion.',
        'assets': assets,
        'font_roots': [{'path': p, 'woff2_count': len(list((root / p).rglob('*.woff2')))}
                       for p in ['static/assets/fonts', 'static/studio/styles/fonts']]}
    if args.file:
        name = safe_relative(args.file).relative_to(root).as_posix()
        print(encoded({'file': name, 'topics': [t['id'] for t in topics if name in t['entrypoints']],
                       'imported_by': sorted(importers.get(name, set())), 'symbols': records.get(name, {}).get('exports', [])}).rstrip())
        return 0 if name in covered else 1
    if not args.index_root:
        context = read_json(root / 'docs/governance/context-check.json')
        registered = set(next((g['docs'] for g in context['groups'] if g['id'] == 'uiux-index'), []))
        documents = {'docs/uiux/' + p.relative_to(index).as_posix() for p in index.rglob('*')
                     if p.is_file() and p.suffix in ('.md', '.json')}
        errors.extend('UIUX file absent from context guard: ' + p for p in sorted(documents - registered))
    if args.refresh and not errors:
        for name, value in generated.items():
            target = index / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(encoded(value), encoding='utf-8')
    if not args.refresh:
        for name, value in generated.items():
            path = index / name
            if not path.is_file() or read_json(path) != value:
                errors.append('Mechanical inventory drift: ' + name)
    # Check links using the final repository location; staging overrides only index documents.
    for path in sorted(index.rglob('*.md')):
        final = root / 'docs/uiux' / path.relative_to(index)
        content = path.read_text(encoding='utf-8-sig')
        for match in re.finditer(r'\]\(([^)]+)\)', content):
            target = match[1].strip().strip('<>')
            if target.startswith(('#', 'https://', 'http://', 'mailto:')):
                continue
            target = unquote(target.split('#', 1)[0])
            if not target:
                continue
            dest = (final.parent / target).resolve()
            if dest.is_relative_to(root / 'docs/uiux'):
                dest = index / dest.relative_to(root / 'docs/uiux')
            if not dest.exists():
                errors.append('Broken link: ' + path.relative_to(index).as_posix() + ' -> ' + target)
    if errors:
        for error in errors:
            print(error)
        return 1
    print(f'UIUX INDEX OK: {len(topics)} topics, {len(modes)} modes, {len(wanted)} frontend files covered, {len(assets)} artwork assets, {len(generated)} mechanical maps. Not behavior/visual acceptance.')
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (ValueError, KeyError, OSError) as exc:
        print('UIUX INDEX ERROR:', exc)
        raise SystemExit(2)
