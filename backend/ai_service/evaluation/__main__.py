"""Usage: python -m backend.ai_service.evaluation --output /tmp/ai-review."""
import argparse
from datetime import datetime, timezone
from html import escape
import json
from pathlib import Path
import subprocess
import webbrowser

from backend.ai_service.evaluation.runner import compare, evaluate

ROOT = Path(__file__).resolve().parents[3]


def git(*args):
    try:
        return subprocess.check_output(['git', *args], cwd=ROOT, text=True, stderr=subprocess.DEVNULL).strip()
    except (OSError, subprocess.CalledProcessError):
        return 'unknown'


def write_artifacts(report, output):
    output.mkdir(parents=True, exist_ok=True)
    (output / 'results.json').write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    # Escape embedded JSON, including customer-controlled closing script tags.
    data = json.dumps(report, ensure_ascii=True).replace('&', '\\u0026').replace('<', '\\u003c').replace('>', '\\u003e')
    template = Path(__file__).with_name('report.html').read_text(encoding='utf-8')
    (output / 'index.html').write_text(template.replace('__REPORT_DATA__', data), encoding='utf-8')
    rows = report['scenarios']
    passed = sum(row['passed'] for row in rows)
    changes = {c['id']: c['state'] for c in report.get('comparison', [])}
    lines = ['# System 2 workflow evaluation', '', f"Offline simulation · {passed}/{len(rows)} scenarios passed · revision {report['metadata']['revision']}", '',
             '| Scenario | Checks | Observed proposals / failures | Baseline |', '|---|---|---|---|']
    svg = ['<svg xmlns="http://www.w3.org/2000/svg" width="1100" height="'+str(140+len(rows)*32)+'" viewBox="0 0 1100 '+str(140+len(rows)*32)+'">', '<rect width="100%" height="100%" fill="#102f40"/>', '<g font-family="sans-serif" fill="#fff">', '<text x="30" y="42" font-size="26">System 2 · Workflow review</text>', f'<text x="30" y="75" font-size="16">Offline simulation · {passed}/{len(rows)} scenarios pass · proposals only</text>']
    failures = []
    for i, row in enumerate(rows):
        outcome = ' → '.join(s['actual'] for s in row['stages'])
        state = 'PASS' if row['passed'] else 'FAIL'
        lines.append(f"| {row['id']} | {state} | {outcome} | {changes.get(row['id'], '—')} |")
        svg.append(f'<text x="30" y="{120+i*32}" font-size="14" fill="{"#83e0c0" if row["passed"] else "#ff9a9a"}">{escape(state+"  "+row["id"])}</text>')
        svg.append(f'<text x="300" y="{120+i*32}" font-size="14">{escape(outcome)}</text>')
        for check in row['checks']:
            if not check['passed']:
                failures.append(f"- `{row['id']}` — {check['name']}")
    for change in report.get('comparison', []):
        if change['state'] == 'removed':
            lines.append(f"| {change['id']} | REMOVED | — | removed |")
    if failures:
        lines += ['', 'Failed checks:', '', *failures]
    lines += ['', 'Open `index.html` for snapshots, progress, checks and full baseline diffs. `overview.svg` is a static PR preview.', '',
              'Scope: offline System 2 only. Reply stages are supplied snapshots. System 1 must separately verify action execution, idempotency and stale proposals after takeover. Live model behavior is not evaluated.']
    (output / 'summary.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    (output / 'overview.svg').write_text('\n'.join(svg + ['</g></svg>']), encoding='utf-8')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=Path('/tmp/system2-review'))
    parser.add_argument('--baseline', type=Path, help='Previously saved results.json (read before writing output)')
    parser.add_argument('--label', default='Working tree')
    parser.add_argument('--open', action='store_true', help='Open the standalone HTML report in the default browser')
    parser.add_argument('--fail-on-change', action='store_true', help='Also exit 1 for any baseline difference, including removed cases')
    args = parser.parse_args()
    if args.fail_on_change and not args.baseline:
        parser.error('--fail-on-change requires --baseline')
    baseline = json.loads(args.baseline.read_text(encoding='utf-8')) if args.baseline else None
    report = evaluate()
    if baseline is not None:
        report['comparison'] = compare(report, baseline)
    report['metadata'] = {'label': args.label, 'revision': git('rev-parse', '--short', 'HEAD'),
                          'dirty': bool(git('status', '--porcelain')), 'generatedAt': datetime.now(timezone.utc).isoformat()}
    write_artifacts(report, args.output)
    passed = sum(row['passed'] for row in report['scenarios'])
    print(f"{passed}/{len(report['scenarios'])} scenarios passed. Report: {(args.output / 'index.html').resolve()}")
    if args.open and not webbrowser.open((args.output / 'index.html').resolve().as_uri()):
        print('Browser opening unavailable; open the report path manually.')
    return int(passed != len(report['scenarios']) or (args.fail_on_change and any(c['state'] != 'unchanged' for c in report.get('comparison', []))))


if __name__ == '__main__':
    raise SystemExit(main())
