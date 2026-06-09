import axios from 'axios'
import type { AxiosInstance, InternalAxiosRequestConfig, AxiosResponse } from 'axios'
import { ElMessage } from 'element-plus'
import router from '@/router'

const service: AxiosInstance = axios.create({
  baseURL: '/api/v1',
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
})

// Request interceptor
service.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    const token = localStorage.getItem('token')
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  (error) => {
    return Promise.reject(error)
  }
)

// Response interceptor
service.interceptors.response.use(
  (response: AxiosResponse) => {
    return response.data
  },
  async (error) => {
    const { response } = error
    
    if (response) {
      switch (response.status) {
        case 401:
          // Try to refresh token
          const refreshToken = localStorage.getItem('refreshToken')
          if (refreshToken && !error.config._retry) {
            error.config._retry = true
            try {
              const res = await axios.post('/api/v1/auth/refresh', {
                refresh_token: refreshToken,
              })
              const { access_token, refresh_token } = res.data
              localStorage.setItem('token', access_token)
              localStorage.setItem('refreshToken', refresh_token)
              error.config.headers.Authorization = `Bearer ${access_token}`
              return service(error.config)
            } catch {
              localStorage.removeItem('token')
              localStorage.removeItem('refreshToken')
              router.push('/login')
            }
          } else {
            localStorage.removeItem('token')
            localStorage.removeItem('refreshToken')
            router.push('/login')
          }
          break
        case 403:
          ElMessage.error('没有权限执行此操作')
          break
        case 404:
          ElMessage.error('请求的资源不存在')
          break
        case 422:
          ElMessage.error(response.data.detail || '请求参数错误')
          break
        case 500:
          ElMessage.error('服务器内部错误')
          break
        default:
          ElMessage.error(response.data.detail || '请求失败')
      }
    } else {
      ElMessage.error('网络连接失败')
    }
    
    return Promise.reject(error)
  }
)

export default service
