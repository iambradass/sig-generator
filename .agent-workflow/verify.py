#!/usr/bin/env python3
"""Run reviewed local checks without deploying, installing, or contacting live systems.

Default: changed files (including untracked nonignored files) and applicable native
checks. --base REV includes committed changes since a base. --full checks every
tracked source file. --checks-only runs only the configured native test commands.
"""
from pathlib import Path
import argparse, ast, fnmatch, html.parser, json, os, re, subprocess, sys, tempfile

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / '.agent-workflow/checks.json'
SKIP = {'.git', 'node_modules', 'vendor', '.next', '.venv', 'venv', '__pycache__',
        'output', 'tmp', 'corpus', '.playwright-cli', 'archive-sandbox'}
RUNTIME = {'.js', '.mjs', '.cjs', '.ts', '.tsx', '.jsx', '.py', '.php', '.html', '.css', '.json', '.sql'}

def git(*args):
    p = subprocess.run(['git', '-C', str(ROOT), *args], capture_output=True)
    if p.returncode:
        raise RuntimeError(p.stderr.decode(errors='replace').strip())
    return p.stdout

def paths(raw):
    return {x.decode('utf-8', errors='surrogateescape') for x in raw.split(b'\0') if x}

def run(argv, label, env=None):
    print('CHECK ' + label, flush=True)
    try:
        result = subprocess.run(argv, cwd=ROOT, env=env, timeout=600, capture_output=True, text=True)
    except (OSError, subprocess.TimeoutExpired) as exc:
        print(f'FAIL {label}: {exc}', flush=True)
        return False
    output = (result.stdout + result.stderr).strip()
    if output:
        print(output[-12000:], flush=True)
    print(('PASS ' if result.returncode == 0 else 'FAIL ') + label, flush=True)
    return result.returncode == 0

class Scripts(html.parser.HTMLParser):
    def __init__(self):
        super().__init__(); self.active = False; self.module = False; self.chunks = []; self.scripts = []
    def handle_starttag(self, tag, attrs):
        if tag != 'script': return
        a = dict(attrs); kind = a.get('type', '').lower()
        self.active = not a.get('src') and kind in ('', 'module', 'text/javascript', 'application/javascript')
        self.module = kind == 'module'; self.chunks = []
    def handle_data(self, data):
        if self.active: self.chunks.append(data)
    def handle_endtag(self, tag):
        if tag == 'script' and self.active:
            self.scripts.append((''.join(self.chunks), self.module)); self.active = False

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base', help='Commit/ref containing the reviewed base, never a shell command')
    parser.add_argument('--full', action='store_true')
    parser.add_argument('--checks-only', action='store_true')
    parser.add_argument('--list', action='store_true', help='Show configured native commands without executing')
    args = parser.parse_args()
    config = json.loads(CONFIG.read_text())
    if args.list:
        print(json.dumps(config, indent=2)); return 0
    if Path(git('rev-parse', '--show-toplevel').decode().strip()).resolve() != ROOT:
        raise RuntimeError('Run this verifier inside its own Git project.')
    has_head = subprocess.run(['git','-C',str(ROOT),'rev-parse','--verify','HEAD'],
                              capture_output=True).returncode == 0
    if has_head:
        changed = paths(git('diff', '--name-only', '-z', 'HEAD', '--'))
    else:
        changed = paths(git('diff', '--name-only', '-z', '--'))
        changed |= paths(git('diff', '--cached', '--name-only', '-z', '--'))
    changed |= paths(git('ls-files', '-z', '--others', '--exclude-standard'))
    if args.base:
        if not has_head: raise ValueError('--base requires a first commit; omit it for an uncommitted new project.')
        base = git('rev-parse', '--verify', '--end-of-options', args.base + '^{commit}').decode().strip()
        changed |= paths(git('diff', '--name-only', '-z', base, 'HEAD', '--'))
    selected = paths(git('ls-files', '-z', '--cached', '--others', '--exclude-standard')) if args.full else changed
    failures = []; checked = 0
    for rel in sorted(selected if not args.checks_only else []):
        path = ROOT / rel
        if not path.is_file() or path.is_symlink() or any(part in SKIP for part in Path(rel).parts): continue
        if any(fnmatch.fnmatch(rel, pat) for pat in config.get('exclude', [])): continue
        suffix = path.suffix.lower()
        if suffix not in RUNTIME: continue
        try:
            body = path.read_text(encoding='utf-8')
            if re.search(r'^(<<<<<<< |>>>>>>> |=======$)', body, re.M):
                raise ValueError('Unresolved merge conflict markers')
            if suffix == '.py': ast.parse(body, filename=rel)
            elif suffix == '.json': json.loads(body)
            elif suffix in {'.js', '.mjs', '.cjs'}:
                if not run(['node', '--check', str(path)], rel): failures.append(rel)
            elif suffix == '.php':
                if not run(['php', '-l', str(path)], rel): failures.append(rel)
            elif suffix == '.html':
                page = Scripts(); page.feed(body)
                for index, (script, module) in enumerate(page.scripts, 1):
                    if not script.strip(): continue
                    with tempfile.NamedTemporaryFile(mode='w', suffix='.mjs' if module else '.cjs') as f:
                        f.write(script); f.flush()
                        label = f'{rel} inline script {index}'
                        if not run(['node', '--check', f.name], label): failures.append(label)
            checked += 1
        except (ValueError, SyntaxError, UnicodeError) as exc:
            print(f'FAIL {rel}: {exc}'); failures.append(rel)
    # Documentation-only changes do not need every application test rerun.
    native_needed = args.full or args.checks_only or any(
        Path(p).suffix.lower() in RUNTIME and not p.startswith('.agent-workflow/')
        and not any(part in SKIP for part in Path(p).parts) for p in changed)
    native = 0
    if native_needed:
        for check in config.get('checks', []):
            argv = check['argv']
            if not isinstance(argv, list) or not argv or not all(isinstance(a,str) for a in argv):
                raise ValueError('Each configured check must use an explicit argv array.')
            env = os.environ.copy(); env.update(check.get('env', {}))
            if not run(argv, check['name'], env): failures.append(check['name'])
            native += 1
    print(f'Checked {checked} source files and {native} native checks; {len(failures)} failures.')
    if not native_needed: print('Native checks skipped: no runtime changes detected. Use --checks-only to run them.')
    if not config.get('checks'): print('Coverage: syntax checks only; browser/behavior verification remains required for relevant changes.')
    return 1 if failures else 0

if __name__ == '__main__':
    try: sys.exit(main())
    except (RuntimeError, ValueError, OSError) as exc:
        print(f'Verification could not complete: {exc}', file=sys.stderr); sys.exit(2)
