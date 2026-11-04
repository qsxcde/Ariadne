<script setup lang="ts">
import { onMounted } from "vue";

import StateBlock from "@/shared/components/StateBlock.vue";
import AlertSettingsSection from "@/pages/settings/AlertSettingsSection.vue";
import ModelSettingsSection from "@/pages/settings/ModelSettingsSection.vue";
import NotificationsSection from "@/pages/settings/NotificationsSection.vue";
import SettingsSection from "@/pages/settings/SettingsSection.vue";
import { useAlertSettings } from "@/pages/settings/useAlertSettings";

defineEmits<{
  back: [];
}>();

const { errorMessage, load } = useAlertSettings();

onMounted(() => {
  void load();
});
</script>

<template>
  <section class="settings-view" aria-label="设置">
    <div class="settings-view__inner">
      <header class="settings-view__bar">
        <div>
          <p class="settings-view__eyebrow">PREFERENCES</p>
          <h1 class="settings-view__title">设置</h1>
          <p class="settings-view__subtitle">本地优先：论文与笔记默认保存在当前设备。</p>
        </div>
        <button type="button" class="settings-view__back" @click="$emit('back')">返回</button>
      </header>

      <div class="settings-view__layout">
        <nav class="settings-view__nav" aria-label="设置分区">
          <a href="#settings-data">数据与隐私</a>
          <a href="#settings-model">模型服务</a>
          <a href="#settings-alerts">提醒与 Digest</a>
          <a href="#settings-notifications">通知</a>
          <a href="#settings-reading">阅读偏好</a>
          <a href="#settings-about">关于 SciPal</a>
        </nav>

        <div class="settings-view__sections">
          <StateBlock
            v-if="errorMessage"
            kind="error"
            compact
            title="设置操作失败"
            :description="errorMessage"
          />

          <SettingsSection id="settings-data" title="数据与隐私" index="01">
            <p>数据目录由后端 SCIPAL_DATA_DIR 控制，默认是 backend/data。</p>
            <p>
              论文原文、解析产物、索引与 SQLite 数据库都保存在本地；未配置远程模型时不会上传论文内容。
            </p>
            <p class="settings-hint">备份：复制 backend/data 目录即可迁移整库。</p>
          </SettingsSection>

          <ModelSettingsSection />

          <AlertSettingsSection />
          <NotificationsSection />

          <SettingsSection id="settings-reading" title="阅读偏好" index="05">
            <p>阅读状态分为：待读、队列中、速读、在读、已读、已归档。</p>
            <p>进度按滚动位置记录；关闭页面后再打开会恢复到上次位置。</p>
            <p class="settings-hint">当前版本只支持文本型 PDF。</p>
          </SettingsSection>

          <SettingsSection id="settings-about" title="关于 SciPal" index="06" last>
            <p>智能论文助手 v0.1 · 个人研究生阅读工作台。</p>
            <p>当前阶段：M0 论文资产层与阅读闭环。</p>
            <p class="settings-hint">后续会加入速读卡、跨论文对比与领域跟进。</p>
          </SettingsSection>
        </div>
      </div>
    </div>
  </section>
</template>

<style scoped>
.settings-view {
  flex: 1;
  min-width: 0;
  overflow-y: auto;
  background: var(--color-page);
}

.settings-view__inner {
  width: 100%;
  max-width: 1200px;
  margin: 0 auto;
  padding: 28px 34px 52px;
}

.settings-view__bar {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  padding-bottom: 22px;
  border-bottom: 1px solid var(--color-border);
}

.settings-view__eyebrow {
  margin: 0 0 6px;
  color: var(--color-text-muted);
  font-family: var(--font-mono);
  font-size: 10px;
  letter-spacing: 0.1em;
}

.settings-view__title {
  margin: 0;
  color: var(--color-text);
  font-family: var(--font-serif);
  font-size: 30px;
  font-weight: 650;
}

.settings-view__subtitle {
  margin: 7px 0 0;
  color: var(--color-text-muted);
  font-size: 12px;
}

.settings-view__back {
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  background: var(--color-surface);
  padding: 7px 13px;
  color: var(--color-text-soft);
  font-size: 12px;
}

.settings-view__back:hover {
  border-color: var(--color-border-strong);
  color: var(--color-text);
}

.settings-view__layout {
  display: grid;
  grid-template-columns: 150px minmax(0, 1fr);
  gap: 48px;
  align-items: start;
  padding-top: 24px;
}

.settings-view__nav {
  position: sticky;
  top: 20px;
  display: flex;
  flex-direction: column;
  border-left: 1px solid var(--color-border);
}

.settings-view__nav a {
  border-left: 2px solid transparent;
  margin-left: -1px;
  padding: 7px 12px;
  color: var(--color-text-muted);
  font-size: 12px;
  text-decoration: none;
}

.settings-view__nav a:hover {
  border-left-color: var(--color-text);
  color: var(--color-text);
}

.settings-view__sections {
  max-width: 820px;
  min-width: 0;
}

@media (max-width: 1100px) {
  .settings-view__layout {
    grid-template-columns: minmax(0, 1fr);
    gap: 20px;
  }

  .settings-view__nav {
    display: none;
  }
}
</style>
