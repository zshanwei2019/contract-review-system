import request from '@/utils/request'

export const authApi = {
  login(data: { username: string; password: string }) {
    return request.post('/auth/login', data)
  },

  refreshToken(refresh_token: string) {
    return request.post('/auth/refresh', { refresh_token })
  },

  getCurrentUser() {
    return request.get('/auth/me')
  },

  changePassword(data: { old_password: string; new_password: string }) {
    return request.put('/auth/password', data)
  },
}
