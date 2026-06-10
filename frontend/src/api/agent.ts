import request from '@/utils/request'

export const agentApi = {
  // ==================== 5-Agent审查 ====================
  multiAgentReview(contractId: number, agents?: string[]) {
    const params = agents ? { agents } : {}
    return request.post(`/agent/multi-agent-review/${contractId}`, null, { params })
  },

  chainReview(contractId: number) {
    return request.post(`/agent/chain-review/${contractId}`)
  },

  listAgents() {
    return request.get('/agent/agents')
  },

  // ==================== 风控规则 ====================
  getRiskRules(category?: string) {
    return request.get('/agent/risk-rules', { params: { category } })
  },

  getPoisonPills() {
    return request.get('/agent/risk-rules/poison-pills')
  },

  analyzeWithRules(text: string, contractCategory: string = 'all') {
    return request.post('/agent/risk-rules/analyze', null, { params: { text, contract_category: contractCategory } })
  },

  getRiskDimensions() {
    return request.get('/agent/risk-rules/dimensions')
  },

  // ==================== 条款分割 ====================
  segmentClauses(contractId: number) {
    return request.post(`/agent/clause-segment/${contractId}`)
  },

  // ==================== 合规追踪 ====================
  checkCompliance(contractId: number) {
    return request.post(`/agent/compliance/check/${contractId}`)
  },

  getComplianceChecklist(contractType: string) {
    return request.get(`/agent/compliance/checklist/${contractType}`)
  },

  // ==================== 报告导出 ====================
  exportReport(contractId: number, format: 'word' | 'pdf' = 'word') {
    return request.get(`/agent/report/export/${contractId}`, {
      params: { format },
      responseType: 'blob',
    })
  },

  // ==================== 向量检索 ====================
  searchContracts(query: string, topK: number = 5) {
    return request.get('/agent/search/contracts', { params: { query, top_k: topK } })
  },

  searchFindings(query: string, topK: number = 5) {
    return request.get('/agent/search/findings', { params: { query, top_k: topK } })
  },

  // ==================== 自学习 ====================
  triggerLearning(limit: number = 100) {
    return request.post('/agent/learning/learn', null, { params: { limit } })
  },

  getLearningStats() {
    return request.get('/agent/learning/stats')
  },

  runFpGrowth(minSupport: number = 2) {
    return request.get('/agent/learning/fp-growth', { params: { min_support: minSupport } })
  },

  // ==================== 监控告警 ====================
  getMonitoringAlerts() {
    return request.get('/agent/monitoring/alerts')
  },

  // ==================== 知识库 ====================
  getLaws(contractType: string = 'all') {
    return request.get('/agent/knowledge/laws', { params: { contract_type: contractType } })
  },

  getCompliance(contractType: string = 'all') {
    return request.get('/agent/knowledge/compliance', { params: { contract_type: contractType } })
  },

  initKnowledge() {
    return request.post('/agent/knowledge/init')
  },

  // ==================== 案例与反馈 ====================
  getSimilarCases(contractType: string, limit: number = 5) {
    return request.get('/agent/cases/similar', { params: { contract_type: contractType, limit } })
  },

  getCaseDetail(caseId: number) {
    return request.get(`/agent/cases/${caseId}`)
  },

  rateCase(caseId: number, rating: number, comment?: string) {
    return request.post(`/agent/cases/${caseId}/rate`, null, { params: { rating, comment } })
  },

  submitCorrection(data: any) {
    return request.post('/agent/corrections', data)
  },

  getCorrectionStats() {
    return request.get('/agent/corrections/stats')
  },

  // ==================== AI配置 ====================
  getAIConfig() {
    return request.get('/agent/ai-config')
  },

  updateAIConfig(data: { base_url: string; model: string; api_key: string }) {
    return request.put('/agent/ai-config', data)
  },

  testAIConnection() {
    return request.post('/agent/test-ai-connection')
  },
}
