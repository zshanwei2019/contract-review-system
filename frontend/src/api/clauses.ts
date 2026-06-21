import request from '@/utils/request'

export const clauseApi = {
  list(params?: { keyword?: string; category?: string; contract_type?: string }) {
    return request.get('/clause-library', { params })
  },

  create(data: { title: string; category: string; content: string; contract_type?: string; risk_level?: string; tags?: string }) {
    return request.post('/clause-library', data)
  },

  update(id: number, data: any) {
    return request.put(`/clause-library/${id}`, data)
  },

  delete(id: number) {
    return request.delete(`/clause-library/${id}`)
  },

  toggleFavorite(id: number, favorite: boolean) {
    if (favorite) {
      return request.delete(`/clause-library/${id}/favorite`)
    }
    return request.post(`/clause-library/${id}/favorite`)
  },

  getFavorites() {
    return request.get('/clause-library/favorites')
  },
}
