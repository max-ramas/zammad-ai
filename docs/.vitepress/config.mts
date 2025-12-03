import { defineConfig } from "vitepress";

// https://vitepress.dev/reference/site-config
export default defineConfig({
  lang: "en-US",
  title: "Zammad-AI",
  description: "GenAI-powered agent for Zammad",
  base: "/zammad-ai/",
  cleanUrls: true,
  lastUpdated: true,
  themeConfig: {
    // https://vitepress.dev/reference/default-theme-config
    nav: [
      { text: "Home", link: "/" },
      { text: "ADR", link: "/adr" },
      { text: "Components", link: "/components" },
    ],

    sidebar: [
      {
        text: "ADR",
        link: "/adr",
        items: [
          {
            text: "01: System architecture",
            link: "/adr/01-system-architecture",
          },
          {
            text: "02: Two-way processing of tickets",
            link: "/adr/02-two-way-processing-of-tickets",
          },
          {
            text: "03: Vector database selection",
            link: "/adr/03-vector-database",
          },
        ],
      },
      {
        text: "Components",
        link: "/components",
        items: [
          {
            text: "Kafka message broker",
            link: "/components/kafka",
          },
        ],
      },
    ],

    socialLinks: [
      { icon: "github", link: "https://github.com/it-at-m/zammad-ai" },
    ],
  },
});
