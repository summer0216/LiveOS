export function rentBudgetMeaning(rent: number, budget: number): string {
  if (rent === budget) return '符合预算';
  return `${rent > budget ? '超出预算' : '低于预算'} ¥${Math.abs(rent - budget).toLocaleString('en-US')}`;
}
