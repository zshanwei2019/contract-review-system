import request from '@/utils/request'

export const risksApi = {
  getCategories() {
    return request.get('/risks/categories')
  },

  getRules(params: any) {
    return request.get('/risks/rules', { params })
  },

  createRule(data: any) {
    return request.post('/risks/rules', data)
  },

  updateRule(id: number, data: any) {
    return request.put(`/risks/rules/${id}`, data)
  },

  getItems(params: any) {
    return request.get('/risks/items', { params })
  },

  updateItem(id: number, data: any) {
    return request.put(`/risks/items/${id}`, data)
  },
  
  initItems() {
    return request.post('/contracts/init-risk-items')
  },
  
  initRules() {
    return request.post('/risks/init-rules')
  },

  // === 风险量化评估 ===
  quantifyItem(itemId: number) {
    return request.post(`/risks/items/${itemId}/quantify`)
  },

  getContractRiskSummary(contractId: number) {
    return request.get(`/risks/contracts/${contractId}/risk-summary`)
  },

  quantifyAllRisks(contractId: number) {
    return request.post(`/risks/contracts/${contractId}/quantify-all`)
  },
}
