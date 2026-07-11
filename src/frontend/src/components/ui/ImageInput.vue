<template>
  <div class="area" @click="inputRef?.click()">
    <d-avatar
      :image="newImage || image"
      size="xlarge"
      :shape="shape"
      style="object-fit: cover"
      :class="{ square: shape === 'square' }"
    />
    <input
      ref="inputRef"
      type="file"
      id="avatar"
      name="avatar"
      accept="image/png, image/jpeg, image/webp"
      class="input"
      @change="onInputChange"
    />
    <span class="link">{{ label }}</span>
  </div>
</template>

<script setup lang="ts">
import avatarPlaceholder from '@/assets/img/avatar-placeholder.png'
import { ref } from 'vue'

type Emits = {
  (e: 'onImageChange', file: File | null): void
}

defineProps({
  image: {
    type: String,
    default: avatarPlaceholder,
  },
  label: {
    type: String,
    default: 'Change photo',
  },
  shape: {
    type: String,
    default: 'circle',
  },
})

const emit = defineEmits<Emits>()

const inputRef = ref<HTMLInputElement>()

const newImage = ref('')

const onInputChange = (event: Event) => {
  const input = event.target as HTMLInputElement

  if (!input.files || !(input.files.length > 0)) {
    emit('onImageChange', null)

    newImage.value = ''

    return
  }

  const file = input.files[0]

  emit('onImageChange', file)

  const reader = new FileReader()

  reader.onload = (e) => {
    newImage.value = (e.target?.result as string) || ''
  }

  reader.readAsDataURL(file)
}
</script>

<style scoped>
.area {
  position: relative;
  display: inline-flex;
  align-items: center;
  gap: 16px;
  cursor: pointer;
}
.input {
  position: absolute;
  top: 0;
  left: 0;
  width: 0;
  height: 0;
  opacity: 0;
}
.square {
  border-radius: 6px;
  overflow: hidden;
}
</style>
