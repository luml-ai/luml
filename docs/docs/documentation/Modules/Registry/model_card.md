---
sidebar_label: 'Cards'
sidebar_position: 1
title: Cards
---

# Cards

Cards provide supplementary information about an artifact in the Registry. They are available on models, experiments, and datasets.

For models and experiments trained in [Express Tasks](../express_tasks.md), cards are generated automatically, displaying an Evaluation Dashboard for traditional ML tasks or the user-built flowchart for LLM workflows. For artifacts produced outside Express Tasks, the card can render any custom HTML component added through the SDK. This makes cards a flexible way to store and present details such as experiment settings, visual outputs, or other contextual information.

***Example 1***

![](/img/model-card1.webp)

***Example 2***
<iframe
  src="/html/example.html"
  style={{
    width: '750px',
    height: '400px',
    border: '2px solid #ccc',
    borderRadius: '10px' 
  }}
/>
