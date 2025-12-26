<template>
  <footer id="footer" class="footer">
    <p>© LUML GmbH 2025</p>
  </footer>
</template>

<script setup lang="ts"></script>

<style scoped>
.footer {
  padding: 8px;
  background-color: var(--p-content-background);
  border-top: 1px solid var(--p-divider-border-color);
  text-align: center;
  color: var(--p-text-muted-color);
  font-size: 10px;
  font-weight: 300;
  line-height: 1.2;
}

.p-overflow-hidden .footer {
  padding-right: calc(var(--p-scrollbar-width) + 8px);
}
</style>
