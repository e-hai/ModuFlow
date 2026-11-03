#!/usr/bin/env python3
import sys, os, re, json
from pathlib import Path

_RELEASE = re.compile(r'^\d+\.\d+\.\d+$')
_REVISION = re.compile(r'^r[1-9]\d*$')
_SOURCE = re.compile(r'工序\s*03|变更单|承接')


def revision_log_rows(content: str):
    """版本表数据行。找不到四列表时返回空列表。"""
    lines = (content or '').splitlines()
    header_at = None
    headers = []
    for index, line in enumerate(lines):
        cells = [cell.strip() for cell in line.strip().strip('|').split('|')]
        if '上线版本' in cells and '稿次' in cells and '来源' in cells and '变更' in cells:
            header_at = index
            headers = cells
            break
    if header_at is None:
        return []
    release_at = headers.index('上线版本')
    revision_at = headers.index('稿次')
    source_at = headers.index('来源')
    rows = []
    for line in lines[header_at + 1:]:
        if not line.strip().startswith('|'):
            break
        cells = [cell.strip() for cell in line.strip().strip('|').split('|')]
        if cells and all(set(cell) <= set('-: ') and cell for cell in cells):
            continue
        if len(cells) <= max(release_at, revision_at, source_at):
            continue
        rows.append({
            'release': cells[release_at],
            'revision': cells[revision_at],
            'source': cells[source_at],
        })
    return rows


def lint_text(content: str, file_name: str = "PRD.md"):
    has_executive_gate = bool(re.search(r'##\s*负责人\s*30\s*秒拍板摘要卡', content))

    expected_chapters = [
        ('Ch0', r'第\s*0\s*章[：:].*元信息|第\s*零\s*章'),
        ('Ch1', r'第一章[：:].*范围|第\s*1\s*章'),
        ('Ch2', r'第二章[：:].*信息架构|第\s*2\s*章'),
        ('Ch3', r'第三章[：:].*详细规格|第\s*3\s*章'),
        ('Ch4', r'第四章[：:].*商业|第\s*4\s*章'),
        ('Ch5', r'第五章[：:].*数据|第\s*5\s*章'),
        ('Ch6', r'第六章[：:].*埋点|第\s*6\s*章'),
        ('Ch7', r'第七章[：:].*验收|第\s*7\s*章'),
    ]
    detected_chapters = []
    missing_chapters = []
    for code, pattern in expected_chapters:
        if re.search(pattern, content):
            detected_chapters.append(code)
        else:
            missing_chapters.append(code)

    views_detected = sorted(list(set(re.findall(r'(?m)^\|\s*([a-z][a-z0-9_]{0,31})\s*\|', content))))
    modules_detected = sorted(list(set(re.findall(r'\bM[1-9]\b', content))))
    table_count = len(re.findall(r'\|(?:\s*[-:]+\s*\|)+', content))
    mermaid_diagrams = len(re.findall(r'```mermaid', content))
    has_banned_smoke_test = bool(re.search(r'工序\s*04\s*假门测试|Smoke\s*Test\s*待回填|Go/Pivot/Kill\s*裁决', content))

    has_sql_ddl = bool(re.search(r'^\s*CREATE\s+(?:TABLE|INDEX)\b', content, re.IGNORECASE | re.MULTILINE))
    has_raw_json_schema = bool(re.search(r'"type"\s*:\s*"(?:object|string|number)"', content))
    has_engineering_leakage = has_sql_ddl or has_raw_json_schema
    revision_rows = revision_log_rows(content)
    revision_problems = []
    if not revision_rows:
        revision_problems.append('版本表需要四列：上线版本、稿次、来源、变更')
    else:
        for row in revision_rows:
            if not _RELEASE.fullmatch(row['release']) or not _REVISION.fullmatch(row['revision']):
                revision_problems.append(
                    f"稿次写成 {row['release']} / {row['revision']}。上线版本用 1.0.0，稿次只写 r1、r2，不要写成 1.0.1"
                )
                break
        if not any(_SOURCE.search(row['source']) for row in revision_rows):
            revision_problems.append('版本表来源要写工序 03、变更单或承接')

    score = 100
    warnings = []
    suggestions = []

    if not has_executive_gate:
        score -= 15
        warnings.append('Missing Executive Gate (负责人 30 秒拍板摘要卡)')
    if missing_chapters:
        score -= min(40, len(missing_chapters) * 8)
        warnings.append('Missing chapters: ' + ', '.join(missing_chapters))
    if not views_detected:
        score -= 10
        warnings.append('No view ids detected. Each page needs a table row whose first cell is a lowercase id such as home')
    if len(modules_detected) < 3:
        score -= 10
        warnings.append('Less than 3 functional modules (M1~Mx) detected')
    if table_count < 5:
        score -= 10
        warnings.append(f'Low structured table count ({table_count}); PRD should be concrete and structured')
    if mermaid_diagrams < 1:
        score -= 5
        suggestions.append('Consider adding Mermaid diagrams for visual flow & state machines')
    if has_banned_smoke_test:
        score -= 20
        warnings.append('PRD contains leftover Stage 04 smoke test tables or Go/Pivot/Kill audit rules')
    if revision_problems:
        score -= 15
        warnings.extend(revision_problems)
    if has_engineering_leakage:
        score -= 25
        leak_details = []
        if has_sql_ddl:
            leak_details.append('SQL DDL (CREATE TABLE/INDEX)')
        if has_raw_json_schema:
            leak_details.append('raw JSON Schema')
        warnings.append('PRD contains engineer-role implementation technical leakages: ' + ', '.join(leak_details) + '. Stage 05 must strictly remain a pure Product Manager role.')

    score = max(0, score)
    passed = score == 100
    return {
        'status': 'ok' if passed else ('warning' if score >= 60 else 'failed'),
        'passed': passed,
        'file': file_name,
        'executive_gate': has_executive_gate,
        'chapters_detected': detected_chapters,
        'missing_chapters': missing_chapters,
        'views_detected': views_detected,
        'modules_detected': modules_detected,
        'table_count': table_count,
        'mermaid_diagrams': mermaid_diagrams,
        'has_banned_smoke_test_table': has_banned_smoke_test,
        'has_engineering_leakage': has_engineering_leakage,
        'warnings': warnings,
        'suggestions': suggestions,
        'score': score
    }


def lint_prd(target_path: Path):
    if not target_path.exists():
        return {
            'status': 'error',
            'passed': False,
            'file': str(target_path),
            'score': 0,
            'errors': [f'File {target_path} does not exist'],
            'warnings': [f'File {target_path} does not exist'],
        }
    return lint_text(target_path.read_text(encoding='utf-8', errors='replace'), target_path.name)

if __name__ == '__main__':
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else (list(Path('.').glob('*.md'))[0] if list(Path('.').glob('*.md')) else Path('PRD.md'))
    result = lint_prd(target)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    sys.exit(0 if result['status'] == 'ok' else 1)
