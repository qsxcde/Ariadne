<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from "vue";
import {
  Bell,
  Calendar,
  DataAnalysis,
  Files,
  Fold,
  Expand,
  Setting,
  SwitchButton,
} from "@element-plus/icons-vue";
import type { CollectionSummary } from "@/api";

const props = defineProps<{
  active: string;
  collections: CollectionSummary[];
  username?: string;
}>();

const emit = defineEmits<{
  navigate: [name: string];
  openCollection: [collectionId: string];
  logout: [];
}>();

const STORAGE_KEY = "scipal.rail.collapsed";
const NARROW_QUERY = "(max-width: 1200px)";
const isNarrow = ref(window.matchMedia(NARROW_QUERY).matches);
const collapsed = ref(
  window.localStorage.getItem(STORAGE_KEY) === "1" || isNarrow.value,
);

const NAV_ITEMS = [
  { name: "today", label: "今天", icon: Calendar },
  { name: "library", label: "文献库", icon: Files },
  { name: "synthesis", label: "综合", icon: DataAnalysis },
  { name: "feed", label: "跟进", icon: Bell },
  { name: "settings", label: "设置", icon: Setting },
] as const;

const initial = computed(() => (props.username || "?").trim().slice(0, 1).toUpperCase());

function toggle(): void {
  collapsed.value = !collapsed.value;
  window.localStorage.setItem(STORAGE_KEY, collapsed.value ? "1" : "0");
}

/** 进入窄屏时自动收起；回到宽屏时恢复用户上次手动选择。 */
function syncViewport(): void {
  const narrow = window.matchMedia(NARROW_QUERY).matches;
  if (narrow && !isNarrow.value) {
    collapsed.value = true;
  } else if (!narrow && isNarrow.value) {
    collapsed.value = window.localStorage.getItem(STORAGE_KEY) === "1";
  }
  isNarrow.value = narrow;
}

onMounted(() => window.addEventListener("resize", syncViewport));
onBeforeUnmount(() => window.removeEventListener("resize", syncViewport));
</script>

<template>
  <nav class="rail" :class="{ 'rail--collapsed': collapsed }" aria-label="主导航">
    <div class="rail__brand">
      <span class="rail__mark">S</span>
      <span v-if="!collapsed" class="rail__name">SciPal</span>
      <button
        type="button"
        class="rail__collapse"
        :aria-label="collapsed ? '展开导航' : '收起导航'"
        @click="toggle"
      >
        <Expand v-if="collapsed" />
        <Fold v-else />
      </button>
    </div>

    <ul class="rail__nav">
      <li v-for="item in NAV_ITEMS" :key="item.name">
        <button
          type="button"
          class="rail__item"
          :class="{ 'is-active': active === item.name }"
          :title="collapsed ? item.label : undefined"
          @click="emit('navigate', item.name)"
        >
          <component :is="item.icon" class="rail__icon" />
          <span v-if="!collapsed" class="rail__label">{{ item.label }}</span>
        </button>
      </li>
    </ul>

    <div v-if="!collapsed && collections.length" class="rail__collections">
      <p class="rail__heading">集合</p>
      <button
        v-for="collection in collections"
        :key="collection.id"
        type="button"
        class="rail__collection"
        :title="collection.name"
        @click="emit('openCollection', collection.id)"
      >
        <span class="rail__dot" aria-hidden="true" />
        <span class="rail__collection-name">{{ collection.name }}</span>
        <span class="rail__count">{{ collection.paper_count }}</span>
      </button>
    </div>

    <div class="rail__footer">
      <span class="rail__avatar" :title="username || '未登录'">{{ initial }}</span>
      <button
        type="button"
        class="rail__logout"
        :title="collapsed ? '退出' : undefined"
        @click="emit('logout')"
      >
        <SwitchButton class="rail__icon" />
        <span v-if="!collapsed">退出</span>
      </button>
    </div>
  </nav>
</template>

<style scoped>
.rail {
  display: flex;
  width: 208px;
  height: 100vh;
  flex-direction: column;
  gap: 18px;
  border-right: 1px solid var(--color-border);
  background: var(--color-sidebar);
  padding: 16px 12px;
}

.rail--collapsed {
  width: 64px;
  align-items: center;
  padding: 16px 8px;
}

.rail__brand {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 0 4px;
}

.rail--collapsed .rail__brand {
  flex-direction: column;
  gap: 6px;
}

.rail__mark {
  display: inline-flex;
  width: 28px;
  height: 28px;
  align-items: center;
  justify-content: center;
  border: 1px solid var(--color-accent);
  border-radius: var(--radius-sm);
  color: var(--color-accent);
  font-family: var(--font-serif);
  font-size: 16px;
  font-weight: 700;
}

.rail__name {
  flex: 1;
  color: var(--color-text);
  font-family: var(--font-serif);
  font-size: 16px;
  font-weight: 650;
  letter-spacing: 0.02em;
}

.rail__collapse {
  display: inline-flex;
  width: 24px;
  height: 24px;
  align-items: center;
  justify-content: center;
  border: 0;
  border-radius: var(--radius-xs);
  background: transparent;
  color: var(--color-text-muted);
}

.rail__collapse:hover {
  color: var(--color-text);
}

.rail__collapse svg {
  width: 14px;
}

.rail__nav {
  display: flex;
  flex-direction: column;
  gap: 2px;
  margin: 0;
  padding: 0;
  list-style: none;
}

.rail__item {
  display: flex;
  width: 100%;
  align-items: center;
  gap: 10px;
  border: 0;
  border-left: 2px solid transparent;
  border-radius: var(--radius-xs);
  background: transparent;
  padding: 9px 10px;
  color: var(--color-text-soft);
  font-size: 13px;
  text-align: left;
}

.rail__item:hover {
  background: var(--color-surface);
  color: var(--color-text);
}

.rail__item.is-active {
  border-left-color: var(--color-text);
  background: var(--color-surface);
  color: var(--color-text);
  font-weight: 600;
}

.rail__icon {
  width: 16px;
  flex: 0 0 16px;
}

.rail--collapsed .rail__item {
  width: 44px;
  justify-content: center;
  border-left-width: 0;
  border-bottom: 2px solid transparent;
  padding: 10px 0;
}

.rail--collapsed .rail__item.is-active {
  border-bottom-color: var(--color-text);
  background: var(--color-surface);
}

.rail__collections {
  display: flex;
  min-height: 0;
  flex: 1;
  flex-direction: column;
  gap: 2px;
  overflow-y: auto;
  border-top: 1px solid var(--color-border);
  padding-top: 12px;
}

.rail__heading {
  margin: 0 10px 6px;
  color: var(--color-text-muted);
  font-family: var(--font-mono);
  font-size: 10px;
  letter-spacing: 0.12em;
  text-transform: uppercase;
}

.rail__collection {
  display: flex;
  align-items: center;
  gap: 8px;
  border: 0;
  border-radius: var(--radius-xs);
  background: transparent;
  padding: 6px 10px;
  color: var(--color-text-soft);
  font-size: 12px;
  text-align: left;
}

.rail__collection:hover {
  background: var(--color-surface);
  color: var(--color-text);
}

.rail__dot {
  width: 5px;
  height: 5px;
  flex: 0 0 5px;
  border-radius: 50%;
  background: var(--color-border-strong);
}

.rail__collection-name {
  overflow: hidden;
  flex: 1;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.rail__count {
  color: var(--color-text-muted);
  font-family: var(--font-mono);
  font-size: 10px;
}

.rail__footer {
  display: flex;
  align-items: center;
  gap: 8px;
  border-top: 1px solid var(--color-border);
  padding-top: 12px;
}

.rail--collapsed .rail__footer {
  flex-direction: column;
}

.rail__avatar {
  display: inline-flex;
  width: 26px;
  height: 26px;
  align-items: center;
  justify-content: center;
  border: 1px solid var(--color-border-strong);
  border-radius: 50%;
  color: var(--color-text-soft);
  font-family: var(--font-mono);
  font-size: 11px;
}

.rail__logout {
  display: flex;
  flex: 1;
  align-items: center;
  gap: 8px;
  border: 0;
  background: transparent;
  color: var(--color-text-muted);
  font-size: 12px;
  text-align: left;
}

.rail__logout:hover {
  color: var(--color-text);
}

.rail--collapsed .rail__logout {
  flex: 0;
  justify-content: center;
}
</style>
