export interface Contract {
  id: number
  contract_no: string
  title: string
  contract_type: ContractType
  status: ContractStatus
  party_a?: string
  party_b?: string
  amount?: number
  currency?: string
  sign_date?: string
  effective_date?: string
  expiry_date?: string
  description?: string
  department?: string
  project_name?: string
  tags?: string[]
  risk_level?: string
  risk_score?: number
  uploader_id: number
  reviewer_id?: number
  created_at: string
  updated_at?: string
  reviewed_at?: string
  approved_at?: string
}

export type ContractType = 
  | 'procurement'
  | 'sales'
  | 'outsourcing'
  | 'equipment'
  | 'lease'
  | 'power_supply'
  | 'nda'
  | 'service'
  | 'construction'
  | 'labor'
  | 'other'

export type ContractStatus = 
  | 'draft'
  | 'pending_review'
  | 'reviewing'
  | 'reviewed'
  | 'pending_approval'
  | 'approved'
  | 'rejected'
  | 'archived'

export interface ContractListParams {
  page?: number
  page_size?: number
  keyword?: string
  contract_type?: ContractType
  status?: ContractStatus
  department?: string
}

export interface ContractCreateData {
  title: string
  contract_type: ContractType
  party_a?: string
  party_b?: string
  amount?: number
  currency?: string
  sign_date?: string
  effective_date?: string
  expiry_date?: string
  description?: string
  department?: string
  project_name?: string
  tags?: string[]
}

export const contractTypeLabels: Record<ContractType, string> = {
  procurement: '采购合同',
  sales: '销售合同',
  outsourcing: '外包合同',
  equipment: '设备合同',
  lease: '租赁合同',
  power_supply: '转供电合同',
  service: '服务合同',
  construction: '工程合同',
  labor: '劳动合同',
  nda: '保密协议',
  other: '其他',
}

export const contractStatusLabels: Record<ContractStatus, string> = {
  draft: '草稿',
  pending_review: '待审查',
  reviewing: '审查中',
  reviewed: '已审查',
  pending_approval: '待审批',
  approved: '已审批',
  rejected: '已驳回',
  archived: '已归档',
}

export const contractStatusColors: Record<ContractStatus, string> = {
  draft: 'info',
  pending_review: 'warning',
  reviewing: 'primary',
  reviewed: 'success',
  pending_approval: 'warning',
  approved: 'success',
  rejected: 'danger',
  archived: 'info',
}
