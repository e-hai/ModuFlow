const ROLE_NAMES: Record<string, string> = {
  mr: '市场研究',
  ba: '商业分析',
  pm: '产品',
  mkt: '增长',
  ux: '设计',
  eng: '研发',
  qa: '测试',
  ops: '运营',
  cmp: '合规',
  lead: '项目总控',
};

export const STAGE_TITLES: Record<string, string> = {
  '01': '市场研究',
  '02': '商业测算',
  '03': '方向决策',
  '04': '小额验证',
  '05': '需求规格',
  '06': '设计',
  '07': '研发',
  '08': '测试',
  '09': '发布',
  '10': '获客',
  '11': '运营复盘',
};

export const STAGE_DECISIONS: Record<string, string> = {
  '01': '市场研究要不要继续',
  '02': '定价能不能做',
  '03': '方向要不要立项',
  '04': '要不要做小额测试',
  '05': '需求能不能封版',
  '06': '设计能不能交给研发',
  '07': '研发能不能交给测试',
  '08': '质量能不能进入发布',
  '09': '能不能提交商店',
  '10': '获客预算能不能批',
  '11': '下一版建议要不要采纳',
};

export function stageDecision(moduleCode?: string | null, fallback?: string): string {
  if (moduleCode && STAGE_DECISIONS[moduleCode]) return STAGE_DECISIONS[moduleCode];
  return fallback || '请您确认这一阶段';
}

export function stageName(moduleCode?: string | null): string {
  if (!moduleCode) return '这一阶段';
  return STAGE_TITLES[moduleCode] || '这一阶段';
}

/** 决策中心不展示工序编号，编号只留在产研工作台。 */
export function withoutStageNumber(text: string): string {
  return text
    .replace(/工序\s*(\d{1,2})/g, (_, raw: string) => STAGE_TITLES[raw.padStart(2, '0')] || '')
    .replace(/[ \t]{2,}/g, ' ')
    .trim();
}

export const STAGE_QUESTIONS: Record<string, string> = {
  '01': '看这份市场研究值不值得继续：有没有算清能拿到的盘子，并写明做不做。',
  '02': '看定价和回收能不能成立。',
  '03': '看这个方向要不要立项。',
  '04': '看小额测试方案能不能拿去试。',
  '05': '看这版需求能不能封版。',
  '06': '看设计的安全区和按钮尺寸过不过关。',
  '07': '看研发交付能不能交给测试。',
  '08': '看还有没有挡住上线的问题。',
  '09': '看能不能提交商店。这一关必须您签字。',
  '10': '看获客预算和成本线能不能批。',
  '11': '看下一版建议有没有留存数据撑着。',
};

export function roleLabel(raw?: string | null): string {
  if (!raw) return '未注明';
  const text = raw.replace(/^agent:/, '').replace(/^human:/, '');
  const name = ROLE_NAMES[text] || text;
  if (raw.startsWith('human:')) return name;
  if (raw.startsWith('agent:') || ROLE_NAMES[text]) return name;
  return text;
}

export function leadActionLabel(action?: string | null): string {
  if (!action) return '';
  if (['approved', 'approve', 'pass', 'passed'].includes(action)) return '建议放行';
  if (['rejected', 'reject', 'kill'].includes(action)) return '建议先别过';
  if (['adjusted', 'adjust', 'pivot'].includes(action)) return '请您先看过再定';
  return action;
}

export function plainLeadRationale(text?: string | null): string {
  if (!text) return '';
  return text.replace(/^【Lead 预评估】/, '').trim();
}

function reviewLine(review: { reviewer?: string; verdict?: string }): string {
  const who = ROLE_NAMES[review.reviewer || ''] || '同事';
  if (review.verdict === 'approve') return `${who}看过，认为可以继续`;
  if (review.verdict === 'request_changes') return `${who}要求再改一版`;
  if (review.verdict === 'raise_cr') return `${who}另外提了变更`;
  return `${who}已复核`;
}

export function evidenceLines(item: unknown): string[] {
  if (typeof item === 'string') {
    return item.split('\n').map((line) => line.trim()).filter(Boolean);
  }
  if (!item || typeof item !== 'object') return [];
  const record = item as Record<string, unknown>;
  const checker = String(record.checker || '');
  if (checker === 'compliance_engine' && Array.isArray(record.findings) && record.findings.length) {
    return record.findings
      .map((line) => String(line).replace(/^\[cmp [^\]]+\]\s*/, '').replace('高敏感系统权限申请: ', '用到了').trim())
      .filter(Boolean);
  }
  if (typeof record.summary === 'string' && record.summary.trim()) {
    return record.summary.split('\n').map((line) => line.trim()).filter(Boolean);
  }
  if (checker === 'deliverable_audit') {
    return [record.passed === false ? '交付物核对没有通过。' : '这一关要求的结论和依据都已写进交付物。'];
  }
  if (checker === 'compliance_engine') {
    if (record.status === 'passed') return ['合规初筛没有发现要停下来的问题。'];
    if (record.status === 'needs_fix') return ['合规初筛还有要改的地方。'];
    return ['合规认为这件事需要法务看过才能继续。'];
  }
  if (checker === 'collaboration_review') {
    if (record.overridden_by) return [`您已决定按当前稿继续（${record.overridden_by}）。`];
    const results = Array.isArray(record.results) ? record.results : [];
    const lines = results
      .filter((review) => review && typeof review === 'object')
      .map((review) => reviewLine(review as { reviewer?: string; verdict?: string }));
    return lines.length ? [`同事复核：${lines.join('；')}。`] : ['同事已经复核过这一稿。'];
  }
  if (checker === 'handoff_repair') {
    return ['补写带上了新的敏感事项。您之前的签字仍然覆盖旧内容，只需要确认这次新加的部分。'];
  }
  return ['这一项已核对。'];
}

export function ruleRequirement(level?: string, status?: string): string {
  if (level === 'red') return '必须您亲自签字';
  if (level === 'yellow') return '请您把关';
  if (status === 'pending') return '请您看过再放行';
  return '已放行';
}
