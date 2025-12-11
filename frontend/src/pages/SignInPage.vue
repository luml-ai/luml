<template>
  <authorization-wrapper title="Sign in" sub-title="Welcome to LUML" :image="MainImage">
    <template #form>
      <d-form
        v-slot="$form"
        class="form"
        ref="formRef"
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
              <d-icon-field>
                <d-input-text
                  ref="emailRef"
                  id="email"
                  name="email"
                  fluid
                  type="text"
                  autocomplete="off"
                  v-model="initialValues.email"
                />
                <d-input-icon>
                  <component
                    :is="getCurrentInputIcon('email')"
                    :size="14"
                    @click="onIconClick('email')"
                  />
                </d-input-icon>
              </d-icon-field>
              <label for="email" class="label">Email</label>
            </d-float-label>
            <d-message v-if="$form.email?.invalid" severity="error" size="small" variant="simple">
              {{ $form.email.error?.message }}
            </d-message>
          </div>
          <div class="input-wrapper">
            <d-float-label variant="on">
              <d-password
                id="password"
                name="password"
                fluid
                autocomplete="off"
                toggleMask
                :feedback="false"
                v-model="initialValues.password"
              />
              <label for="password" class="label">Password</label>
            </d-float-label>
            <d-message
              v-if="$form.password?.invalid"
              severity="error"
              size="small"
              variant="simple"
            >
              {{ $form.password.error?.message }}
            </d-message>
          </div>
        </div>
        <d-button type="submit" label="Sign in" rounded />
        <d-message v-if="formResponseError" severity="error" size="small" variant="simple">
          {{ formResponseError }}
        </d-message>
      </d-form>
    </template>
    <template #footer>
      <div class="footer-message">
        <span>Don`t have an account? </span>
        <router-link :to="{ name: 'sign-up' }" class="link">Sign up</router-link>
      </div>
      <router-link :to="{ name: 'forgot-password' }" class="link">Forgot password?</router-link>
    </template>
  </authorization-wrapper>
</template>

<script setup lang="ts">
import type { FormSubmitEvent } from '@primevue/forms'
import type { IPostSignInRequest } from '@/lib/api/api.interfaces'

import { ref, watch } from 'vue'

import AuthorizationWrapper from '@/components/authorization/AuthorizationWrapper.vue'
import MainImage from '@/assets/img/form-bg.webp'

import { signInInitialValues } from '@/utils/forms/initialValues'
import { signInResolver } from '@/utils/forms/resolvers'

import { useAuthStore } from '@/stores/auth'
import { useRouter } from 'vue-router'
import { useInputIcon } from '@/hooks/useInputIcon'

const authStore = useAuthStore()
const router = useRouter()

const initialValues = ref(signInInitialValues)
const resolver = ref(signInResolver)

const formRef = ref()
const emailRef = ref<HTMLInputElement | null>(null)
const formResponseError = ref('')

const { getCurrentInputIcon, onIconClick } = useInputIcon([emailRef], formRef, initialValues, false)

const onFormSubmit = async ({ valid, values }: FormSubmitEvent) => {
  if (!valid) return

  const data: IPostSignInRequest = {
    email: values.email,
    password: values.password,
  }

  try {
    await authStore.signIn(data)

    router.push({ name: 'home' })
  } catch (e: any) {
    const errorDetails = e.response?.data.detail

    if (typeof errorDetails === 'string') formResponseError.value = e.response.data.detail
    else if (typeof errorDetails === 'object') {
      formResponseError.value = errorDetails[0]?.msg
    } else formResponseError.value = 'Form is invalid'
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
.form {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.inputs {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.input-wrapper {
  display: flex;
  flex-direction: column;
  gap: 7px;
}

.footer-message {
  margin-bottom: 16px;
}
</style>
