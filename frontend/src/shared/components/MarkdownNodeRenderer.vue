<script setup lang="ts">
/**
 * Renders a constrained markdown node tree recursively so rich text stays
 * component-driven and avoids unsafe HTML injection.
 */
import MathContent from "@/shared/components/MathContent.vue";
import type { MarkdownAllowedTag, MarkdownNode } from "@/shared/utils/markdown";

defineProps<{
  node: MarkdownNode;
}>();

function resolveTag(tag: MarkdownAllowedTag): MarkdownAllowedTag {
  return tag;
}
</script>

<template>
  <MathContent v-if="node.math" :display="node.math === 'block'" :text="node.text ?? ''" />
  <span v-else-if="node.tag === null">{{ node.text }}</span>
  <component :is="resolveTag(node.tag)" v-else>
    <MarkdownNodeRenderer v-for="child in node.children" :key="child.id" :node="child" />
  </component>
</template>
