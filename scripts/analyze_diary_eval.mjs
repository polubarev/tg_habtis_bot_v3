import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';

const root = path.resolve(process.argv[2] || 'docs/evals/2026-10-22/main');
const fixtures = JSON.parse(fs.readFileSync(path.join(root, 'fixtures.json'), 'utf8'));
const run = JSON.parse(fs.readFileSync(path.join(root, 'run.json'), 'utf8'));
const rows = fs.readFileSync(path.join(root, 'responses.jsonl'), 'utf8').trim().split('\n').filter(Boolean).map(JSON.parse);
const key = r => `${r.model}|${r.repeat}|${r.caseId}|${r.phase}|${r.turn}`;
const latest = [...new Map(rows.map(r => [key(r), r])).values()];
const caseMap = new Map(fixtures.cases.map(c => [c.id, c]));
const ambiguous = r => r.caseId === 'sensitive_and_uncertain' && r.turn === 0;
const equal = (a, b) => Array.isArray(b) ? Array.isArray(a) && a.length === b.length && [...a].sort().join('|') === [...b].sort().join('|') : a === b;
const percent = (a, b) => b ? Number((100 * a / b).toFixed(2)) : null;
const quantile = (items, q) => items.length ? items[Math.min(items.length - 1, Math.ceil(items.length * q) - 1)] : null;
const metrics = [];
for (const model of run.modelMetadata) {
  for (const phase of ['baseline', 'unified']) {
    const calls = latest.filter(r => r.model === model.id && r.phase === phase);
    const ok = calls.filter(r => r.status === 'ok' && r.assessment.schemaErrors.length === 0);
    const expectedCalls = run.repeats * fixtures.cases.reduce((n, c) => n + (phase === 'baseline' ? 1 : c.turns.length), 0);
    const counters = { all: [0, 0], known: [0, 0], unknown: [0, 0], explicitZeroOrFalse: [0, 0], unambiguous: [0, 0] };
    const mismatches = [];
    for (const r of ok) {
      const fixture = caseMap.get(r.caseId).turns[r.turn];
      const actual = phase === 'unified' ? r.payload.habits : r.payload;
      for (const [field, want] of Object.entries(fixture.expected)) {
        const match = equal(actual[field], want);
        const groups = ['all', want === null ? 'unknown' : 'known'];
        if (want === 0 || want === false) groups.push('explicitZeroOrFalse');
        if (!(ambiguous(r) && field === 'общение')) groups.push('unambiguous');
        for (const group of groups) { counters[group][1]++; if (match) counters[group][0]++; }
        if (!match) mismatches.push({ case: r.caseId, turn: r.turn + 1, repeat: r.repeat, field, expected: want, actual: actual[field], ambiguousLabel: ambiguous(r) && field === 'общение' });
      }
    }
    const shortLatency = ok.filter(r => !caseMap.get(r.caseId).long).map(r => r.latencyMs).sort((a, b) => a - b);
    const checkTotals = {};
    for (const r of ok) for (const c of r.assessment.checks) {
      const group = c.id.split(':')[0];
      checkTotals[group] ||= { passed: 0, total: 0 };
      checkTotals[group].total++;
      if (c.pass) checkTotals[group].passed++;
    }
    const fullChains = phase === 'unified' ? fixtures.cases.reduce((n, c) => n + Array.from({ length: run.repeats }, (_, i) => ok.filter(r => r.caseId === c.id && r.repeat === i + 1).length === c.turns.length ? 1 : 0).reduce((a, b) => a + b, 0), 0) : null;
    metrics.push({ model: model.id, phase, expectedCalls, attemptedCalls: calls.length, validCalls: ok.length, endToEndSuccessPercent: percent(ok.length, expectedCalls), perfectExtractionTurns: ok.filter(r => r.assessment.mismatches.length === 0).length, extraction: Object.fromEntries(Object.entries(counters).map(([k, [matched, total]]) => [k, { matched, total, percent: percent(matched, total) }])), mismatches, fullChains, checkTotals, failedChecks: ok.flatMap(r => r.assessment.checks.filter(c => !c.pass).map(c => ({ case: r.caseId, turn: r.turn + 1, repeat: r.repeat, id: c.id }))), shortLatencyP50Ms: quantile(shortLatency, .5), shortLatencyP90Ms: quantile(shortLatency, .9), billedCostUsd: calls.reduce((n, r) => n + (r.billedCostUsd || 0), 0), missingBillingCalls: calls.filter(r => r.billedCostUsd == null).length, reasoningTokens: calls.reduce((n, r) => n + (r.response?.usage?.completion_tokens_details?.reasoning_tokens || 0), 0), failures: calls.filter(r => !ok.includes(r)).map(r => ({ case: r.caseId, repeat: r.repeat, turn: r.turn + 1, finishReason: r.response?.choices?.[0]?.finish_reason, error: r.response?.error || r.error, parseError: r.parseError })), longOutputs: ok.filter(r => caseMap.get(r.caseId).long && phase === 'unified').map(r => ({ repeat: r.repeat, turn: r.turn + 1, chars: r.payload.diary.length, seconds: r.latencyMs / 1000, factsMatched: r.assessment.checks.filter(c => c.id.startsWith('fact:') && c.pass).length, factsTotal: r.assessment.checks.filter(c => c.id.startsWith('fact:')).length })) });
  }
}
fs.writeFileSync(path.join(root, 'analysis.json'), JSON.stringify({ createdAt: new Date().toISOString(), recordedCalls: rows.length, expectedCalls: run.expectedCalls, totalBilledCostUsd: rows.reduce((n, r) => n + (r.billedCostUsd || 0), 0), labelAmbiguity: 'sensitive_and_uncertain, turn 1, общение: spouse leaving a note can be interpreted as family communication; exclude this one field from unambiguous metric for all models/phases/repeats', metrics }, null, 2));

const groups = new Map();
for (const r of latest.filter(r => r.status === 'ok' && r.phase === 'unified')) {
  const c = caseMap.get(r.caseId);
  if (c.long || r.turn !== c.turns.length - 1) continue;
  const id = crypto.createHash('sha256').update(`${c.id}|${r.payload.diary}`).digest('hex').slice(0, 10);
  if (!groups.has(id)) groups.set(id, { id, case: c.id, userTurns: c.turns.map(t => t.text), diary: r.payload.diary, count: 0, records: [] });
  const group = groups.get(id);
  group.count++;
  group.records.push({ model: r.model, repeat: r.repeat, case: c.id });
}
const sorted = [...groups.values()].sort((a, b) => a.id.localeCompare(b.id));
fs.writeFileSync(path.join(root, 'review-key.json'), JSON.stringify(sorted.map(({ id, records }) => ({ id, records })), null, 2));
fs.writeFileSync(path.join(root, 'review-packet.json'), JSON.stringify(sorted.map(({ records, ...rest }) => rest), null, 2));
fs.writeFileSync(path.join(root, 'review-packet.md'), sorted.map(g => `## ${g.id} (${g.case}, ${g.count} identical finals)\n\n${g.userTurns.map((t, i) => `User ${i + 1}: ${t}`).join('\n\n')}\n\nDiary:\n${g.diary}\n`).join('\n'));
console.log(JSON.stringify({ rows: rows.length, expected: run.expectedCalls, reviewGroups: groups.size, finalShortSamples: sorted.reduce((n, g) => n + g.count, 0), metrics: metrics.map(({ mismatches, failedChecks, failures, longOutputs, ...m }) => ({ ...m, mismatches: mismatches.length, failedChecks: failedChecks.length, failures: failures.length, longOutputs })) }, null, 2));
