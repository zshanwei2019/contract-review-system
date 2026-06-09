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
}
