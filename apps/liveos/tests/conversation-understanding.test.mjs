import assert from 'node:assert/strict';
import test from 'node:test';
import { understandingRows } from '../features/first-conversation/understanding.ts';

test('backend requirements are presented without upgrading understanding into verified Reality', () => {
  const rows = understandingRows({
    work_location: '南山', commute_minutes: 30, budget: 6000, layout_requirement: null,
    geographic_identity: '不得替代用户工作地点', geographic_status: 'GROUNDED',
  });
  assert.deepEqual(rows, [
    { label: '工作地点', value: '南山', status: '理解中' },
    { label: '通勤要求', value: '不超过 30 分钟', status: '理解中' },
    { label: '预算范围', value: '约 6,000 元 / 月', status: '理解中' },
    { label: '居住偏好', value: '未明确', status: '未明确' },
  ]);
});

test('absent, blank or invalid fields stay explicitly unknown rather than receiving example defaults', () => {
  const rows = understandingRows({ work_location: '  ', commute_minutes: NaN, budget: -1 });
  assert.equal(rows.length, 4);
  assert.ok(rows.every((row) => row.value === '未明确' && row.status === '未明确'));
});

test('zero and actual housing requirements are preserved rather than replaced by missing-value fallbacks', () => {
  const rows = understandingRows({ work_location: null, commute_minutes: 0, budget: 0, layout_requirement: '两居，整租' });
  assert.equal(rows[1].value, '不超过 0 分钟');
  assert.equal(rows[2].value, '约 0 元 / 月');
  assert.equal(rows[3].value, '两居，整租');
});
