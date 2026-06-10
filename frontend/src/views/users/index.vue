<template>
  <div class="users">
    <el-card shadow="hover">
      <template #header>
        <div class="card-header">
          <span>用户管理</span>
          <el-button type="primary" icon="Plus" @click="showDialog = true">新建用户</el-button>
        </div>
      </template>
      
      <div class="search-bar">
        <el-input v-model="searchForm.keyword" placeholder="搜索用户名、姓名、邮箱" prefix-icon="Search" clearable style="width: 300px" @keyup.enter="handleSearch" />
        <el-button type="primary" icon="Search" @click="handleSearch">搜索</el-button>
      </div>
      
      <el-table v-loading="loading" :data="users" stripe border>
        <el-table-column prop="username" label="用户名" width="120" />
        <el-table-column prop="name" label="姓名" width="120" />
        <el-table-column prop="email" label="邮箱" width="200" />
        <el-table-column prop="department" label="部门" width="120" />
        <el-table-column prop="is_active" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="row.is_active ? 'success' : 'danger'" size="small">{{ row.is_active ? '启用' : '禁用' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="last_login" label="最后登录" width="180">
          <template #default="{ row }">{{ row.last_login ? formatDate(row.last_login) : '-' }}</template>
        </el-table-column>
        <el-table-column label="操作" width="200" fixed="right">
          <template #default="{ row }">
            <el-button text type="primary" size="small" @click="handleEdit(row)">编辑</el-button>
            <el-button text type="danger" size="small" @click="handleDelete(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
      
      <div class="pagination">
        <el-pagination v-model:current-page="pagination.page" v-model:page-size="pagination.page_size" :total="pagination.total" layout="total, prev, pager, next" @size-change="handleSearch" @current-change="handleSearch" />
      </div>
    </el-card>
    
    <el-dialog v-model="showDialog" :title="editingUser ? '编辑用户' : '新建用户'" width="500px">
      <el-form :model="form" label-width="80px">
        <el-form-item label="用户名" required><el-input v-model="form.username" :disabled="!!editingUser" /></el-form-item>
        <el-form-item label="姓名" required><el-input v-model="form.name" /></el-form-item>
        <el-form-item label="邮箱" required><el-input v-model="form.email" /></el-form-item>
        <el-form-item label="密码" :required="!editingUser"><el-input v-model="form.password" type="password" :placeholder="editingUser ? '留空不修改' : '请输入密码'" /></el-form-item>
        <el-form-item label="部门"><el-input v-model="form.department" /></el-form-item>
        <el-form-item label="职位"><el-input v-model="form.position" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showDialog = false">取消</el-button>
        <el-button type="primary" @click="handleSave">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { usersApi } from '@/api/users'
import { ElMessage, ElMessageBox } from 'element-plus'
import dayjs from 'dayjs'

const loading = ref(false)
const users = ref<any[]>([])
const showDialog = ref(false)
const editingUser = ref<any>(null)
const searchForm = reactive({ keyword: '' })
const pagination = reactive({ page: 1, page_size: 20, total: 0 })
const form = reactive({ username: '', name: '', email: '', password: '', department: '', position: '' })

const formatDate = (d: string) => dayjs(d).format('YYYY-MM-DD HH:mm')

const fetchUsers = async () => {
  loading.value = true
  try {
    const params: any = {
      page: pagination.page,
      page_size: pagination.page_size,
    }
    if (searchForm.keyword) params.keyword = searchForm.keyword
    
    const res = await usersApi.list(params)
    users.value = res.items || []
    pagination.total = res.total || 0
  } catch {} finally { loading.value = false }
}

const handleSearch = () => { pagination.page = 1; fetchUsers() }

const handleEdit = (row: any) => {
  editingUser.value = row
  Object.assign(form, { ...row, password: '' })
  showDialog.value = true
}

const handleSave = async () => {
  try {
    if (editingUser.value) {
      const data: any = { ...form }
      if (!data.password) delete data.password
      await usersApi.update(editingUser.value.id, data)
    } else {
      await usersApi.create(form)
    }
    ElMessage.success('保存成功')
    showDialog.value = false
    fetchUsers()
  } catch { ElMessage.error('保存失败') }
}

const handleDelete = async (row: any) => {
  await ElMessageBox.confirm(`确定删除用户 ${row.name}？`, '警告', { type: 'error' })
  try { await usersApi.delete(row.id); ElMessage.success('删除成功'); fetchUsers() } catch { ElMessage.error('删除失败') }
}

onMounted(() => { fetchUsers() })
</script>

<style scoped>
.card-header { display: flex; justify-content: space-between; align-items: center; }
.search-bar { display: flex; gap: 12px; margin-bottom: 16px; }
.pagination { margin-top: 16px; display: flex; justify-content: flex-end; }
</style>
