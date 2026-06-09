export interface UserInfo {
  id: number
  username: string
  email: string
  name: string
  phone?: string
  avatar?: string
  department?: string
  position?: string
  is_active: boolean
  is_superuser: boolean
  roles: Role[]
  last_login?: string
  created_at: string
}

export interface Role {
  id: number
  name: string
  code: string
  description?: string
  is_active: boolean
}

export interface Permission {
  id: number
  name: string
  code: string
  type: string
  path?: string
}
