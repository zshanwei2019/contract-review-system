import request from '@/utils/request'

export const usersApi = {
  list(params: any) {
    return request.get('/users', { params })
  },

  get(id: number) {
    return request.get(`/users/${id}`)
  },

  create(data: any) {
    return request.post('/users', data)
  },

  update(id: number, data: any) {
    return request.put(`/users/${id}`, data)
  },

  delete(id: number) {
    return request.delete(`/users/${id}`)
  },

  getRoles() {
    return request.get('/users/roles/list')
  },

  createRole(data: any) {
    return request.post('/users/roles', data)
  },
}
