import request from '@/utils/request'

export const dashboardApi = {
  getStats() {
    return request.get('/dashboard/stats')
  },

  getMyTasks() {
    return request.get('/dashboard/my-tasks')
  },
}
