<script setup lang="ts">
import { ref } from "vue";
import { useRouter } from "vue-router";
import { ElMessage } from "element-plus";
import { useAuth } from "../composables/useAuth";
import { toErrorMessage } from "../utils/error";

const router = useRouter();
const { loginUser, registerUser } = useAuth();

const username = ref("");
const password = ref("");
const isRegister = ref(false);
const submitting = ref(false);

async function submit(): Promise<void> {
  if (!username.value.trim() || !password.value) {
    ElMessage.warning("请输入用户名和密码");
    return;
  }
  submitting.value = true;
  try {
    if (isRegister.value) {
      await registerUser(username.value.trim(), password.value);
    } else {
      await loginUser(username.value.trim(), password.value);
    }
    await router.push({ name: "today" });
  } catch (error: unknown) {
    ElMessage.error(toErrorMessage(error, "操作失败"));
  } finally {
    submitting.value = false;
  }
}

function toggleMode(): void {
  isRegister.value = !isRegister.value;
}
</script>

<template>
  <div class="login-view">
    <section class="login-view__card">
      <header class="login-view__header">
        <span class="login-view__mark" aria-hidden="true">SP</span>
        <h1 class="login-view__title">SciPal</h1>
        <p class="login-view__subtitle">学术论文阅读助手 · 让引用可追溯</p>
      </header>

      <el-form class="login-view__form" @submit.prevent="submit">
        <el-form-item>
          <el-input
            v-model="username"
            placeholder="用户名"
            :disabled="submitting"
            @keyup.enter="submit"
          />
        </el-form-item>
        <el-form-item>
          <el-input
            v-model="password"
            type="password"
            placeholder="密码"
            :disabled="submitting"
            show-password
            @keyup.enter="submit"
          />
        </el-form-item>
        <el-form-item>
          <el-button
            type="primary"
            :loading="submitting"
            class="login-view__submit"
            @click="submit"
          >
            {{ isRegister ? "注册并进入" : "登录" }}
          </el-button>
        </el-form-item>
      </el-form>

      <p class="login-view__toggle">
        {{ isRegister ? "已有账号？" : "没有账号？" }}
        <a href="#" @click.prevent="toggleMode">
          {{ isRegister ? "去登录" : "去注册" }}
        </a>
      </p>
    </section>
  </div>
</template>

<style scoped>
.login-view {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100vh;
  background: var(--color-page);
}

.login-view__card {
  width: min(380px, calc(100vw - 48px));
  padding: 38px 36px 34px;
  background: var(--color-surface);
  border: 1px solid var(--color-border-strong);
  border-radius: var(--radius-sm);
  box-shadow: none;
}

.login-view__header {
  margin-bottom: 26px;
  padding-bottom: 22px;
  border-bottom: 1px solid var(--color-border);
  text-align: center;
}

.login-view__mark {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 36px;
  height: 36px;
  margin-bottom: 14px;
  border: 1px solid var(--color-accent);
  border-radius: var(--radius-xs);
  color: var(--color-accent);
  background: transparent;
  font-family: var(--font-serif);
  font-size: 18px;
  font-weight: 700;
}

.login-view__title {
  margin: 0 0 6px;
  color: var(--color-text);
  font-family: var(--font-serif);
  font-size: 28px;
  font-weight: 650;
  letter-spacing: 0.01em;
}

.login-view__subtitle {
  margin: 0;
  font-size: 13px;
  color: var(--color-text-muted);
}

.login-view__submit {
  width: 100%;
}

.login-view__toggle {
  margin: 0;
  font-size: 13px;
  text-align: center;
  color: var(--color-text-muted);
}

.login-view__toggle a {
  color: var(--color-accent);
  text-decoration: none;
}
</style>
