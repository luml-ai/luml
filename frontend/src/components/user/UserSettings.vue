<template>
  <d-form
    class="wrapper"
    ref="formRef"
    v-slot="$form"
    :initialValues
    :resolver
    :validateOnValueUpdate="false"
    :validateOnSubmit="true"
    :validateOnBlur="true"
    @submit="onFormSubmit"
  >
    <d-avatar
      :label="userStore.getUserAvatar ? undefined : getUserFullName?.[0] || getUserEmail?.[0]"
      :image="userStore.getUserAvatar"
      shape="circle"
      size="xlarge"
      class="image-input"
    ></d-avatar>
    <div class="inputs">
      <div class="input-wrapper">
        <d-float-label variant="on">
          <d-icon-field>
            <d-input-text
              ref="usernameRef"
              id="username"
              name="username"
              fluid
              v-model="initialValues.username"
            />
            <d-input-icon>
              <component
                :is="getCurrentInputIcon('username')"
                :size="14"
                @click="onIconClick('username')"
              />
            </d-input-icon>
          </d-icon-field>
          <label class="label" for="username">Name</label>
        </d-float-label>
        <d-message v-if="$form.username?.invalid" severity="error" size="small" variant="simple">
          {{ $form.username.error?.message }}
        </d-message>
      </div>
      <div class="input-wrapper">
        <d-float-label variant="on">
          <d-icon-field>
            <d-input-text id="email" :model-value="getUserEmail" fluid readonly />
            <d-input-icon v-if="!isUserLoggedWithSSO">
              <button
                type="button"
                class="field-action"
                aria-label="Change email"
                @click="$emit('showChangeEmail')"
              >
                <pencil-line :size="14" />
              </button>
            </d-input-icon>
          </d-icon-field>
          <label class="label" for="email">Email</label>
        </d-float-label>
        <small v-if="isUserLoggedWithSSO">Email is managed by your sign-in provider.</small>
      </div>
      <div v-if="!isUserLoggedWithSSO" class="input-wrapper">
        <d-float-label variant="on">
          <d-icon-field>
            <d-input-text id="password" model-value="••••••••" fluid readonly />
            <d-input-icon>
              <button
                type="button"
                class="field-action"
                aria-label="Change password"
                @click="$emit('showChangePassword')"
              >
                <pencil-line :size="14" />
              </button>
            </d-input-icon>
          </d-icon-field>
          <label class="label" for="password">Password</label>
        </d-float-label>
      </div>
    </div>
    <d-message v-if="formResponseError" severity="error" size="small" variant="simple">
      {{ formResponseError }}
    </d-message>
    <div class="footer">
      <d-button
        label="Delete account"
        severity="warn"
        variant="outlined"
        @click="isDeleteAccountVisible = true"
      />
      <d-button label="Save changes" type="submit" :disabled="userStore.isUserDisabled" />
    </div>
    <DeleteAccountModal v-model:show="isDeleteAccountVisible" />
  </d-form>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import type { FormSubmitEvent } from '@primevue/forms'
import { PencilLine } from 'lucide-vue-next'

import { useInputIcon } from '@/hooks/useInputIcon'
import { useUserStore } from '@/stores/user'
import { useToast } from 'primevue/usetoast'

import type { IUpdateUserRequest } from '@/lib/api/api.interfaces'
import { userSettingResolver } from '@/utils/forms/resolvers'
import { userProfileUpdateSuccessToast } from '@/lib/primevue/data/toasts'
import { storeToRefs } from 'pinia'
import { getErrorMessage } from '@/helpers/helpers'
import DeleteAccountModal from './DeleteAccountModal.vue'

const userStore = useUserStore()
const { getUserFullName, getUserEmail, isUserLoggedWithSSO } = storeToRefs(userStore)

const toast = useToast()

type Emits = {
  showChangeEmail: []
  showChangePassword: []
  close: []
}

const emit = defineEmits<Emits>()

const initialValues = ref({
  username: getUserFullName.value || '',
})
const resolver = ref(userSettingResolver)

const formRef = ref()
const usernameRef = ref<HTMLInputElement | null>()

const { getCurrentInputIcon, onIconClick } = useInputIcon([usernameRef], formRef, initialValues)

const isDeleteAccountVisible = ref(false)
const formResponseError = ref('')

const showSuccess = (detail?: string) => {
  toast.add(userProfileUpdateSuccessToast(detail))
}

const onFormSubmit = async ({ valid }: FormSubmitEvent) => {
  if (!valid) return

  const data: IUpdateUserRequest = {}

  if (userStore.getUserFullName !== initialValues.value.username)
    data.full_name = initialValues.value.username

  if (!Object.keys(data).length) {
    emit('close')
    return
  }

  try {
    const response = await userStore.updateUser(data)

    showSuccess(response.detail)
    emit('close')
  } catch (e: unknown) {
    formResponseError.value = getErrorMessage(e, 'Form is invalid')
  }
}

watch(
  initialValues,
  () => {
    formResponseError.value = ''
  },
  { deep: true },
)
</script>

<style scoped>
.wrapper {
  display: flex;
  flex-direction: column;
}

.image-input {
  align-self: flex-start;
  margin-bottom: 24px;
}

.inputs {
  display: flex;
  flex-direction: column;
  gap: 24px;
  margin-bottom: 12px;
}

.field-action {
  display: flex;
  padding: 0;
  border: none;
  background: none;
  color: inherit;
  cursor: pointer;
}

.footer {
  padding-top: 32px;
  display: flex;
  justify-content: space-between;
}

.input-wrapper {
  display: flex;
  flex-direction: column;
  gap: 7px;
}
</style>
