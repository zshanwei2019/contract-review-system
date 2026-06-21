import request from '@/utils/request'

export const templateApi = {
  list(params?: { contract_type?: string; status?: string }) {
    return request.get('/templates', { params })
  },

  get(id: number) {
    return request.get(`/templates/${id}`)
  },

  create(data: { name: string; contract_type: string; content: string; description?: string; variables?: string }) {
    return request.post('/templates', data)
  },

  update(id: number, data: any) {
    return request.put(`/templates/${id}`, data)
  },

  delete(id: number) {
    return request.delete(`/templates/${id}`)
  },

  publish(id: number) {
    return request.post(`/templates/${id}/publish`)
  },

  instantiate(id: number, data: { variables: Record<string, string>; title?: string }) {
    return request.post(`/templates/${id}/instantiate`, data)
  },
}
