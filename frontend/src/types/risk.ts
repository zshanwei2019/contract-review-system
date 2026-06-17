// 风险规则相关类型与标签映射

// 风险规则适用类型(从 risk_rules_engine 数据)
// 注意: 风险规则的 contract_type 包含 "procurement" / "sales" / "outsourcing"
//      / "lease" / "logistics" + 多个组合值(如 "procurement,sales")
//      与合同类型 (contractType) 不完全相同, 这里单独定义
export type RiskRuleContractType =
  | 'procurement'
  | 'sales'
  | 'outsourcing'
  | 'lease'
  | 'logistics'
  | '' // 空 = 通用

export const riskRuleContractTypeLabels: Record<string, string> = {
  procurement: '采购',
  sales: '销售',
  outsourcing: '外协',
  lease: '租赁',
  logistics: '物流',
  all: '通用',
}

// 转换单条规则适用类型为中文(支持多值)
// 'procurement,sales' => '采购,销售'
// '' / null / undefined => '通用'
export function formatRiskRuleContractType(value: string | null | undefined): string {
  if (!value || value === 'all') return '通用'

  // 拆分多值
  const codes = value.split(',').map(s => s.trim()).filter(Boolean)
  const labels = codes.map(c => riskRuleContractTypeLabels[c] || c)
  return labels.join('、')
}

// 风险等级标签与颜色
export const riskLevelLabels: Record<string, string> = {
  high: '高风险',
  medium: '中风险',
  low: '低风险',
  none: '无风险',
}

export const riskLevelColors: Record<string, string> = {
  high: 'danger',
  medium: 'warning',
  low: 'info',
  none: 'success',
}

// 风险等级 chip 颜色 (Tailwind / Element Plus type 值)
export const riskLevelTagType: Record<string, 'danger' | 'warning' | 'info' | 'success' | 'primary'> = {
  high: 'danger',
  medium: 'warning',
  low: 'info',
  none: 'success',
}
