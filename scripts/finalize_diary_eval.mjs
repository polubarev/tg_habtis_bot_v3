import fs from 'node:fs';
import path from 'node:path';

const root = path.resolve(process.argv[2] || 'docs/evals/2026-10-22');
const read = name => JSON.parse(fs.readFileSync(path.join(root, name), 'utf8'));
const records = suite => fs.readFileSync(path.join(root, suite, 'responses.jsonl'), 'utf8').trim().split('\n').filter(Boolean).map(JSON.parse);
const reviews = read('manual-review.json');
const groups = read('main/review-key.json');
const manual = {};
for (const group of groups) {
  const review = reviews.reviews[group.id];
  if (!review) throw new Error(`Missing manual review ${group.id}`);
  for (const record of group.records) {
    manual[record.model] ||= { finalDrafts: 0, substantiveIssues: [], minorIssues: [], scoreSums: [0, 0, 0, 0] };
    const model = manual[record.model];
    model.finalDrafts++;
    review.scores.forEach((value, index) => { model.scoreSums[index] += value; });
    const observation = { case: record.case, repeat: record.repeat, reviewId: group.id, note: review.note };
    if (review.scores.includes(0)) model.substantiveIssues.push(observation);
    else if (review.scores.includes(1)) model.minorIssues.push(observation);
  }
}
fs.writeFileSync(path.join(root, 'manual-summary.json'), JSON.stringify(manual, null, 2));
const finalScores = groups.flatMap(group => group.records.map(record => ({ ...record, ...reviews.reviews[group.id], reviewId: group.id })));
const reviewedModels = [...new Set(finalScores.map(r => r.model))];
const finalKeys = [...new Set(finalScores.map(r => `${r.case}|${r.repeat}`))].filter(key => reviewedModels.every(model => finalScores.some(r => r.model === model && `${r.case}|${r.repeat}` === key)));
const balancedManual = reviewedModels.map(model => {
  const comparable = finalScores.filter(r => r.model === model && finalKeys.includes(`${r.case}|${r.repeat}`));
  return { model, comparableFinals: comparable.length, substantiveIssues: comparable.filter(r => r.scores.includes(0)).map(r => ({ case: r.case, repeat: r.repeat, reviewId: r.reviewId, note: r.note })), minorIssues: comparable.filter(r => !r.scores.includes(0) && r.scores.includes(1)).length };
});
fs.writeFileSync(path.join(root, 'balanced-manual.json'), JSON.stringify({ note: 'Only identical case/repeat finals available and reviewed for every model; this does not replace missing-output coverage.', caseRepeatKeys: finalKeys, results: balancedManual }, null, 2));

const holdout = records('holdout');
const consistency = holdout.filter(r => r.phase === 'unified' && r.turn === 1 && r.status === 'ok').map(r => {
  const matches = [...r.payload.diary.matchAll(/Настроение оцениваю на (\d+)/gu)].map(m => Number(m[1]));
  return { model: r.model, repeat: r.repeat, habitMood: r.payload.habits.настроение, diaryMoodMentions: matches, mismatch: matches.some(value => value !== r.payload.habits.настроение), note: 'Post-hoc observation after reading outputs; not part of the frozen automatic primary checks' };
});
fs.writeFileSync(path.join(root, 'holdout-consistency.json'), JSON.stringify(consistency, null, 2));

const mainRows = records('main');
const uniqueKey = r => `${r.model}|${r.repeat}|${r.caseId}|${r.phase}|${r.turn}`;
const latest = [...new Map(mainRows.map(r => [uniqueKey(r), r])).values()];
const commonKeys = new Set(latest.filter(r => r.phase === 'unified' && r.caseId !== 'long_diary').map(r => `${r.caseId}|${r.repeat}|${r.turn}`));
const balanced = [];
const modelIds = read('main/run.json').modelMetadata.map(m => m.id);
for (const key of [...commonKeys]) {
  const matching = latest.filter(r => r.phase === 'unified' && `${r.caseId}|${r.repeat}|${r.turn}` === key && r.status === 'ok');
  if (modelIds.some(id => !matching.some(r => r.model === id))) commonKeys.delete(key);
}
for (const model of modelIds) {
  const matching = latest.filter(r => r.model === model && r.phase === 'unified' && commonKeys.has(`${r.caseId}|${r.repeat}|${r.turn}`));
  balanced.push({ model, comparableShortCalls: matching.length, billedCostUsd: matching.reduce((n, r) => n + (r.billedCostUsd || 0), 0), costPer100CallsUsd: matching.reduce((n, r) => n + (r.billedCostUsd || 0), 0) / matching.length * 100 });
}
const all = [...mainRows, ...holdout, ...records('smoke')];
const totals = { totalCallsIncludingSmoke: all.length, mainCallsIncludingRecovery: mainRows.length, holdoutCalls: holdout.length, smokeCalls: records('smoke').length, knownBilledCostUsd: all.reduce((n, r) => n + (r.billedCostUsd || 0), 0), missingBillingCalls: all.filter(r => r.billedCostUsd == null).length, explicitRateLimitCalls: all.filter(r => r.httpStatus === 429).length, conservativeBudgetChargeUsd: all.reduce((n, r) => n + (r.budgetChargeUsd || 0), 0), balancedShortCosts: balanced };
fs.writeFileSync(path.join(root, 'totals.json'), JSON.stringify(totals, null, 2));

const examples = [];
for (const r of latest.filter(r => r.status === 'ok' && r.phase === 'unified' && ['explicit_corrections', 'sensitive_and_uncertain', 'negations_other_people', 'ambiguous_time'].includes(r.caseId))) {
  const fixture = read('main/fixtures.json').cases.find(c => c.id === r.caseId);
  if (r.turn !== fixture.turns.length - 1) continue;
  examples.push({ model: r.model, case: r.caseId, repeat: r.repeat, userTurns: fixture.turns.map(t => t.text), output: r.payload });
}
fs.writeFileSync(path.join(root, 'examples.json'), JSON.stringify(examples, null, 2));

// Supplementary, application-equivalent list normalization. Keep raw strict
// scores untouched: an empty list is normalized to None by the bot's list code.
const normalization = [];
const cases = new Map(read('main/fixtures.json').cases.map(c => [c.id, c]));
for (const model of modelIds) for (const phase of ['baseline', 'unified']) {
  let matched = 0;
  let total = 0;
  const issues = [];
  for (const r of latest.filter(r => r.model === model && r.phase === phase && r.status === 'ok' && r.assessment.schemaErrors.length === 0)) {
    const actual = phase === 'unified' ? r.payload.habits : r.payload;
    const expected = cases.get(r.caseId).turns[r.turn].expected;
    for (const [field, want] of Object.entries(expected)) {
      if (r.caseId === 'sensitive_and_uncertain' && r.turn === 0 && field === 'общение') continue;
      const value = field === 'общение' && Array.isArray(actual[field]) && actual[field].length === 0 ? null : actual[field];
      const equal = Array.isArray(want) ? Array.isArray(value) && value.length === want.length && [...value].sort().join('|') === [...want].sort().join('|') : value === want;
      total++;
      if (equal) matched++;
      else issues.push({ case: r.caseId, repeat: r.repeat, turn: r.turn + 1, field, expected: want, actual: value });
    }
  }
  normalization.push({ model, phase, matched, total, percent: total ? matched / total * 100 : null, issues });
}
fs.writeFileSync(path.join(root, 'normalized-extraction.json'), JSON.stringify({ note: 'Supplementary metric: exclude the fixed ambiguous family-note label and normalize [] to null for the multi-choice field. Original strict metrics are unchanged.', results: normalization }, null, 2));

// Verify that persisted snapshots still match the exact data used for each call.
for (const suite of ['main', 'holdout', 'smoke']) {
  const fixture = read(`${suite}/fixtures.json`);
  if (records(suite).some(r => r.fixtureSha256 !== fixture.sha256)) throw new Error(`Fixture mismatch in ${suite}`);
}
// Print only a count if a credential were ever accidentally echoed by a provider.
const dotenv = fs.readFileSync(path.resolve('.env'), 'utf8');
const rawKey = dotenv.match(/^\s*OPENROUTER_API_KEY\s*=\s*(.*?)\s*$/m)?.[1]?.replace(/^['"]|['"]$/g, '');
if (rawKey && rawKey.length > 15 && JSON.stringify(all).includes(rawKey)) throw new Error('Credential found in an evaluation artifact: do not share');
console.log(JSON.stringify({ totals, manual, holdoutConsistency: consistency }, null, 2));
