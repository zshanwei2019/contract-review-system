import request from '@/utils/request'

export const workflowsApi = {
  // ========== 工作流定义 ==========
  getDefinitions() {
    return request.get('/workflows/definitions')
  },

  createDefinition(data: any) {
    return request.post('/workflows/definitions', data)
  },

  // ========== 工作流实例 ==========
  getInstances(params?: { contractId?: number; status?: string }) {
    return request.get('/workflows/instances', { params })
  },

  getInstance(id: number) {
    return request.get(`/workflows/instances/${id}`)
  },

  createInstance(data: { workflowId: number; contractId: number }) {
    return request.post('/workflows/instances', data)
  },

  stepAction(instanceId: number, stepId: number, data: { action: string; remark?: string }) {
    return request.post(`/workflows/instances/${instanceId}/steps/${stepId}/action`, data)
  },
}
