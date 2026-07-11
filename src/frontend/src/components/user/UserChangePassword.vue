<template>
  <d-form
    class="wrapper"
    v-slot="$form"
    :initialValues
    :resolver
    :validateOnValueUpdate="false"
    :validateOnSubmit="true"
    :validateOnBlur="true"
    @submit="onFormSubmit"
  >
    <div class="inputs">
      <div class="input-wrapper">
        <d-float-label variant="on">
          <d-password
            id="oldPassword"
            name="current_password"
            :feedback="false"
            fluid
            toggleMask
            v-model="initialValues.current_password"
          />
          <label class="label" for="oldPassword">Old password</label>
        </d-float-label>
        <d-message
          v-if="$form.current_password?.invalid"
          severity="error"
          size="small"
          variant="simple"
        >
          {{ $form.current_password.error?.message }}
        </d-message>
      </div>
      <div class="input-wrapper">
        <d-float-label variant="on">
          <d-password
            id="newPassword"
            name="new_password"
            :feedback="false"
            fluid
            toggleMask
            v-model="initialValues.new_password"
          />
          <label class="label" for="newPassword">New password</label>
        </d-float-label>
        <d-message
          v-if="$form.new_password?.invalid"
          severity="error"
          size="small"
          variant="simple"
        >
          {{ $form.new_password.error?.message }}
        </d-message>
      </div>
      <div class="input-wrapper">
        <d-float-label variant="on">
          <d-password
            id="confirmPassword"
            name="confirmPassword"
            :feedback="false"
            fluid
            toggleMask
            v-model="initialValues.confirmPassword"
          />
          <label class="label" for="confirmPassword">Confirm password</label>
        </d-float-label>
        <d-message
          v-if="$form.confirmPassword?.invalid"
          severity="error"
          size="small"
          variant="simple"
        >
          {{ $form.confirmPassword.error?.message }}
        </d-message>
      </div>
      <d-message v-if="formResponseError" severity="error" size="small" variant="simple">
        {{ formResponseError }}
      </d-message>
    </div>
    <div class="footer">
      <d-button label="save changes" type="submit" />
    </div>
  </d-form>
</template>

<script setup lang="ts">
import type { FormSubmitEvent } from '@primevue/forms'
import { ref, watch } from 'vue'
import { useUserStore } from '@/stores/user'
import { userChangePasswordResolver } from '@/utils/forms/resolvers'
import { userChangePasswordInitialValues } from '@/utils/forms/initialValues'
import { getErrorMessage } from '@/helpers/helpers'

const emit = defineEmits(['success'])

const userStore = useUserStore()

const initialValues = ref(userChangePasswordInitialValues)
const resolver = ref(userChangePasswordResolver)
const formResponseError = ref('')

const onFormSubmit = async ({ valid, values }: FormSubmitEvent) => {
  if (!valid) return

  const data = {
    current_password: values.current_password,
    new_password: values.new_password,
  }

  try {
    await userStore.changePassword(data)

    emit('success')
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
  padding-top: 10px;
}
.inputs {
  display: flex;
  flex-direction: column;
  gap: 20px;
  margin-bottom: 32px;
}

.input-wrapper {
  display: flex;
  flex-direction: column;
  gap: 5px;
}

.footer {
  display: flex;
  justify-content: flex-end;
}
</style>
