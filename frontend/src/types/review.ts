export interface ReviewTask {
  id: number
  contract_id: number
  reviewer_id: number
  assigned_by: number
  status: ReviewTaskStatus
  risk_level?: string
  risk_score?: number
  summary?: string
  deadline?: string
  started_at?: string
  completed_at?: string
  created_at: string
  contract?: any
  reviewer?: any
}

export type ReviewTaskStatus = 
  | 'pending'
  | 'in_progress'
  | 'completed'
  | 'cancelled'

export interface ReviewOpinion {
  id: number
  review_task_id: number
  reviewer_id: number
  opinion_type: OpinionType
  content: string
  suggestion?: string
  risk_level?: string
  clause_reference?: string
  legal_basis?: string
  created_at: string
}

export type OpinionType = 
  | 'risk'
  | 'suggestion'
  | 'modification'
  | 'approval'

export const reviewTaskStatusLabels: Record<ReviewTaskStatus, string> = {
  pending: '待处理',
  in_progress: '进行中',
  completed: '已完成',
  cancelled: '已取消',
}

export const opinionTypeLabels: Record<OpinionType, string> = {
  risk: '风险提示',
  suggestion: '改进建议',
  modification: '修改意见',
  approval: '审批意见',
}
