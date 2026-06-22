import request from '@/utils/request'

export const integrationApi = {
  listConfigs(params?: any) {
    return request.get('/integration/configs', { params })
  },
  createConfig(data: any) {
    return request.post('/integration/configs', data)
  },
  updateConfig(id: number, data: any) {
    return request.put(`/integration/configs/${id}`, data)
  },
  deleteConfig(id: number) {
    return request.delete(`/integration/configs/${id}`)
  },
  testConnection(id: number) {
    return request.post(`/integration/configs/${id}/test`)
  },
  triggerSync(id: number) {
    return request.post(`/integration/configs/${id}/sync`)
  },
  listWebhooks(params?: any) {
    return request.get('/integration/webhooks', { params })
  },
  listSyncLogs(params?: any) {
    return request.get('/integration/sync-logs', { params })
  },
  stats() {
    return request.get('/integration/stats')
  },
}
