import type { LivingProfile } from '@/services/profile';

type Requirements = Pick<LivingProfile, 'work_location' | 'commute_minutes' | 'budget' | 'layout_requirement'>;

/** Format backend understanding only; Profile does not provide user-confirmation provenance. */
export function understandingRows(profile: Requirements) {
  const text = (value: string | null | undefined) => value?.trim() || null;
  const number = (value: number | null, format: (value: number) => string) => (
    value !== null && Number.isFinite(value) && value >= 0 ? format(value) : null
  );
  return [
    { label: '工作地点', value: text(profile.work_location) },
    { label: '通勤要求', value: number(profile.commute_minutes, (value) => `不超过 ${value} 分钟`) },
    { label: '预算范围', value: number(profile.budget, (value) => `约 ${value.toLocaleString('zh-CN')} 元 / 月`) },
    { label: '居住偏好', value: text(profile.layout_requirement) },
  ].map(({ label, value }) => ({ label, value: value ?? '未明确', status: value === null ? '未明确' : '理解中' }));
}
