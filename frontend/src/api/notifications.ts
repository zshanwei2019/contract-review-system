import request from '@/utils/request'

export const notificationsApi = {
  list(params: any) {
    return request.get('/notifications', { params })
  },

  getCount() {
    return request.get('/notifications/count')
  },

  markRead(id: number) {
    return request.put(`/notifications/${id}/read`)
  },

  markAllRead() {
    return request.put('/notifications/read-all')
  },

  delete(id: number) {
    return request.delete(`/notifications/${id}`)
  },
}
