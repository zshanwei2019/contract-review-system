import request from '@/utils/request'

export const workflowsApi = {
  getDefinitions() {
    return request.get('/workflows/definitions')
  },

  createDefinition(data: any) {
    return request.post('/workflows/definitions', data)
  },

  getInstance(id: number) {
    return request.get(`/workflows/instances/${id}`)
  },

  createInstance(data: any) {
    return request.post('/workflows/instances', data)
  },

  stepAction(instanceId: number, stepId: number, data: any) {
    return request.post(`/workflows/instances/${instanceId}/steps/${stepId}/action`, data)
  },
}
