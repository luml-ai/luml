---
sidebar_label: 'Model Card'
sidebar_position: 1
title: Model Card
---

# Model Card
Model Cards provide supplementary information about a model. They are generated automatically for models trained in [Express Tasks](../../express_tasks.md), displaying an Evaluation Dashboard for traditional ML tasks or the user-built flowchart for LLM workflows. For models trained outside Express Tasks, the card can render any custom HTML component added through the SDK. This makes Model Cards a flexible way to store and present details such as experiment settings, visual outputs, and other contextual information.

***Example 1***

![](/img/model-card1.png)

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