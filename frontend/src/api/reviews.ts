import request from '@/utils/request'

export const reviewsApi = {
  list(params: any) {
    return request.get('/reviews', { params })
  },

  get(id: number) {
    return request.get(`/reviews/${id}`)
  },

  create(data: any) {
    return request.post('/reviews', data)
  },

  update(id: number, data: any) {
    return request.put(`/reviews/${id}`, data)
  },

  createOpinion(taskId: number, data: any) {
    return request.post(`/reviews/${taskId}/opinions`, data)
  },

  getOpinions(taskId: number) {
    return request.get(`/reviews/${taskId}/opinions`)
  },
}
