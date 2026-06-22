<template>
  <div class="profile">
    <el-row :gutter="20">
      <!-- 左侧：个人信息 -->
      <el-col :span="14">
        <el-card shadow="hover">
          <template #header><span>个人信息</span></template>
          <el-descriptions :column="2" border>
            <el-descriptions-item label="用户名">{{ userStore.userInfo?.username }}</el-descriptions-item>
            <el-descriptions-item label="姓名">{{ userStore.userInfo?.name }}</el-descriptions-item>
            <el-descriptions-item label="邮箱">{{ userStore.userInfo?.email }}</el-descriptions-item>
            <el-descriptions-item label="部门">{{ userStore.userInfo?.department || '-' }}</el-descriptions-item>
            <el-descriptions-item label="职位">{{ userStore.userInfo?.position || '-' }}</el-descriptions-item>
            <el-descriptions-item label="角色">{{ roleLabels }}</el-descriptions-item>
            <el-descriptions-item label="最后登录">{{ userStore.userInfo?.last_login ? formatDate(userStore.userInfo.last_login) : '-' }}</el-descriptions-item>
            <el-descriptions-item label="账号状态">
              <el-tag type="success" size="small">正常</el-tag>
            </el-descriptions-item>
          </el-descriptions>
        </el-card>
      </el-col>

      <!-- 右侧：修改密码 -->
      <el-col :span="10">
        <el-card shadow="hover">
          <template #header><span>修改密码</span></template>
          <el-form :model="pwdForm" :rules="pwdRules" ref="pwdFormRef" label-width="100px">
            <el-form-item label="当前密码" prop="old_password">
              <el-input v-model="pwdForm.old_password" type="password" show-password placeholder="输入当前密码" />
            </el-form-item>
            <el-form-item label="新密码" prop="new_password">
              <el-input v-model="pwdForm.new_password" type="password" show-password placeholder="至少6位" />
            </el-form-item>
            <el-form-item label="确认新密码" prop="confirm_password">
              <el-input v-model="pwdForm.confirm_password" type="password" show-password placeholder="再次输入新密码" />
            </el-form-item>
            <el-form-item>
              <el-button type="primary" @click="handleChangePassword" :loading="changing">确认修改</el-button>
              <el-button @click="resetPwdForm">重置</el-button>
            </el-form-item>
          </el-form>
        </el-card>
      </el-col>
    </el-row>

    <!-- 我的合同统计 -->
    <el-card shadow="hover" style="margin-top: 20px">
      <template #header><span>我的合同统计</span></template>
      <el-row :gutter="20">
        <el-col :span="6">
          <el-statistic title="已创建" :value="myStats.created" />
        </el-col>
        <el-col :span="6">
          <el-statistic title="待审查" :value="myStats.pending" />
        </el-col>
        <el-col :span="6">
          <el-statistic title="已通过" :value="myStats.approved" />
        </el-col>
        <el-col :span="6">
          <el-statistic title="已签署" :value="myStats.signed" />
        </el-col>
      </el-row>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import { useUserStore } from '@/stores/user'
import { ElMessage, type FormInstance, type FormRules } from 'element-plus'
import request from '@/utils/request'
import dayjs from 'dayjs'

const userStore = useUserStore()
const formatDate = (d: string) => dayjs(d).format('YYYY-MM-DD HH:mm')

const roleLabels = computed(() => {
  const roles = (userStore.userInfo as any)?.roles || []
  const map: Record<string, string> = { admin: '管理员', superadmin: '超级管理员', reviewer: '审查员', editor: '编辑' }
  return roles.map((r: string) => map[r] || r).join('、') || '普通用户'
})

// 修改密码
const pwdFormRef = ref<FormInstance>()
const changing = ref(false)
const pwdForm = reactive({ old_password: '', new_password: '', confirm_password: '' })
const pwdRules: FormRules = {
  old_password: [{ required: true, message: '请输入当前密码', trigger: 'blur' }],
  new_password: [
    { required: true, message: '请输入新密码', trigger: 'blur' },
    { min: 6, message: '至少6位', trigger: 'blur' },
  ],
  confirm_password: [
    { required: true, message: '请确认新密码', trigger: 'blur' },
    {
      validator: (_rule: any, value: string, callback: any) => {
        if (value !== pwdForm.new_password) callback(new Error('两次输入不一致'))
        else callback()
      },
      trigger: 'blur',
    },
  ],
}

const handleChangePassword = async () => {
  if (!pwdFormRef.value) return
  await pwdFormRef.value.validate(async (valid) => {
    if (!valid) return
    changing.value = true
    try {
      await request.put('/auth/password', {
        old_password: pwdForm.old_password,
        new_password: pwdForm.new_password,
      })
      ElMessage.success('密码修改成功')
      resetPwdForm()
    } catch (e: any) {
      ElMessage.error(e?.response?.data?.detail || '密码修改失败')
    } finally {
      changing.value = false
    }
  })
}

const resetPwdForm = () => {
  pwdForm.old_password = ''
  pwdForm.new_password = ''
  pwdForm.confirm_password = ''
  pwdFormRef.value?.clearValidate()
}

// 我的统计
const myStats = reactive({ created: 0, pending: 0, approved: 0, signed: 0 })

onMounted(async () => {
  try {
    const res = await request.get('/dashboard/stats')
    const s = res.data || res
    myStats.created = s.total_contracts || 0
    myStats.pending = s.pending_reviews || 0
    myStats.approved = s.approved_reviews || 0
    myStats.signed = s.signed_contracts || 0
  } catch {}
})
</script>

<style scoped>
.profile { max-width: 1200px; margin: 0 auto; }
</style>
