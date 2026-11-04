import js from "@eslint/js";
import globals from "globals";
import pluginVue from "eslint-plugin-vue";
import tseslint from "typescript-eslint";
import prettier from "eslint-config-prettier";
import { defineConfig, globalIgnores } from "eslint/config";

const FEATURES = ["chat", "library", "reader", "sessions"];

export default defineConfig([
  globalIgnores(["dist", "node_modules"]),
  {
    files: ["**/*.{ts,vue}"],
    extends: [js.configs.recommended, ...tseslint.configs.recommended],
    languageOptions: {
      globals: globals.browser,
    },
    rules: {
      // TS 已负责未定义标识符检查，no-undef 会误报 DOM 类型
      "no-undef": "off",
      "no-console": ["warn", { allow: ["warn", "error"] }],
      "@typescript-eslint/consistent-type-imports": [
        "error",
        { prefer: "type-imports", fixStyle: "separate-type-imports" },
      ],
    },
  },
  ...pluginVue.configs["flat/recommended"],
  {
    files: ["**/*.vue"],
    languageOptions: {
      parserOptions: {
        parser: tseslint.parser,
      },
    },
  },
  // 业务域边界：features/* 只能依赖共用层与自身域，不能依赖编排层或别的域
  ...FEATURES.map((feature) => ({
    files: [`src/features/${feature}/**/*.{ts,vue}`],
    rules: {
      "no-restricted-imports": [
        "error",
        {
          patterns: [
            {
              group: ["@/app/**", "@/pages/**", "@/main"],
              message: "features 不得依赖编排层（app/router/main/pages）",
            },
            {
              group: FEATURES.filter((other) => other !== feature).map(
                (other) => `@/features/${other}/components/**`,
              ),
              message: "features 之间不得跨域引用组件，改为经 store 或共用 shared/ 交互",
            },
          ],
        },
      ],
    },
  })),
  // 关闭与 Prettier 冲突的格式规则，格式一律交给 prettier 决定
  prettier,
]);
