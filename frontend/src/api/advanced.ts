import request from '@/utils/request'

/**
 * 高级 AI 审查 API
 * 对应后端 /api/v1/ 下无 prefix 路由
 */
export const advancedApi = {
  // ========== 条款级审查 ==========
  clauseReview(contractId: number) {
    return request.post(`/contracts/${contractId}/clause-review`)
  },

  // ========== 语义比对 ==========
  compareContracts(originalText: string, revisedText: string) {
    return request.post('/contracts/compare', {
      original_text: originalText,
      revised_text: revisedText,
    })
  },
  compareVersions(contractId: number, versionA: number, versionB: number) {
    return request.post(`/contracts/${contractId}/compare-versions`, {
      version_a: versionA,
      version_b: versionB,
    })
  },

  // ========== 相对方画像 ==========
  getPartyProfile(partyName: string) {
    return request.get(`/parties/${encodeURIComponent(partyName)}/profile`)
  },
  getExternalRisk(partyName: string, internalRiskScore?: number) {
    return request.get(`/parties/${encodeURIComponent(partyName)}/external-risk`, {
      params: internalRiskScore !== undefined ? { internal_risk_score: internalRiskScore } : {},
    })
  },

  // ========== 义务清单 ==========
  getObligations(contractId: number) {
    return request.get(`/contracts/${contractId}/obligations`)
  },

  // ========== 谈判策略 ==========
  getPlaybook(contractId: number) {
    return request.get(`/contracts/${contractId}/playbook`)
  },

  // ========== 双语合同审查 (P3) ==========
  bilingualReview(cnText: string, enText: string, contractType?: string) {
    return request.post('/contracts/bilingual-review', {
      cn_text: cnText,
      en_text: enText,
      contract_type: contractType || 'other',
    })
  },
  bilingualReviewByContract(contractId: number, cnText?: string, enText?: string) {
    return request.post(`/contracts/${contractId}/bilingual-review`, {
      cn_text: cnText || null,
      en_text: enText || null,
    })
  },

  // ========== 法规合规 (P3) ==========
  complianceCheck(contractText: string, contractType?: string) {
    return request.post('/contracts/compliance-check', {
      contract_text: contractText,
      contract_type: contractType || 'other',
    })
  },
  complianceCheckByContract(contractId: number) {
    return request.post(`/contracts/${contractId}/compliance-check`)
  },
  searchRegulations(query: string, category?: string) {
    return request.get('/regulations/search', {
      params: { query, ...(category ? { category } : {}) },
    })
  },
  getRegulationUpdates(sinceDate?: string) {
    return request.get('/regulations/updates', {
      params: sinceDate ? { since_date: sinceDate } : {},
    })
  },
  assessRegulationImpact(contractText: string, contractType?: string) {
    return request.post('/contracts/regulation-impact', {
      contract_text: contractText,
      contract_type: contractType || 'other',
    })
  },
}
