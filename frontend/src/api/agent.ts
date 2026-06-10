import request from '@/utils/request'

export const agentApi = {
  // 多Agent审查
  multiAgentReview(contractId: number, agents?: string[]) {
    const params = agents ? { agents } : {}
    return request.post(`/agent/multi-agent-review/${contractId}`, null, { params })
  },

  // 推理链审查
  chainReview(contractId: number) {
    return request.post(`/agent/chain-review/${contractId}`)
  },

  // 监控告警
  getMonitoringAlerts() {
    return request.get('/agent/monitoring/alerts')
  },

  // 知识库
  getLaws(contractType: string = 'all') {
    return request.get('/agent/knowledge/laws', { params: { contract_type: contractType } })
  },

  getCompliance(contractType: string = 'all') {
    return request.get('/agent/knowledge/compliance', { params: { contract_type: contractType } })
  },

  initKnowledge() {
    return request.post('/agent/knowledge/init')
  },

  // 案例
  getSimilarCases(contractType: string, limit: number = 5) {
    return request.get('/agent/cases/similar', { params: { contract_type: contractType, limit } })
  },

  getCaseDetail(caseId: number) {
    return request.get(`/agent/cases/${caseId}`)
  },

  rateCase(caseId: number, rating: number, comment?: string) {
    return request.post(`/agent/cases/${caseId}/rate`, null, { params: { rating, comment } })
  },

  // 修正
  submitCorrection(data: any) {
    return request.post('/agent/corrections', data)
  },

  getCorrectionStats() {
    return request.get('/agent/corrections/stats')
  },

  // Agent列表
  listAgents() {
    return request.get('/agent/agents')
  },
}
