<template>
  <authorization-wrapper title="Sign up" sub-title="Welcome to LUML" :image="MainImage">
    <template #form>
      <d-form
        class="form"
        ref="formRef"
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
              <d-icon-field>
                <d-input-text
                  ref="usernameRef"
                  id="username"
                  name="username"
                  fluid
                  type="text"
                  autocomplete="off"
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
              <label for="username" class="label">Name</label>
            </d-float-label>
            <d-message
              v-if="$form.username?.invalid"
              severity="error"
              size="small"
              variant="simple"
            >
              {{ $form.username.error?.message }}
            </d-message>
          </div>
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
            <d-message v-if="$form.password?.invalid" severity="error" size="small" variant="simple"
              >{{ $form.password.error?.message }}
            </d-message>
          </div>
        </div>
        <d-button type="submit" label="Sign up" rounded />
        <d-message v-if="formResponseError" severity="error" size="small" variant="simple">
          {{ formResponseError }}
        </d-message>
      </d-form>
    </template>
    <template #footer>
      <span>Already have an account? </span>
      <router-link :to="{ name: 'sign-in' }" class="link">Sign in</router-link>
    </template>
  </authorization-wrapper>
</template>

<script setup lang="ts">
import AuthorizationWrapper from '@/components/authorization/AuthorizationWrapper.vue'
import MainImage from '@/assets/img/form-bg.webp'

import { ref, watch } from 'vue'
import type { FormSubmitEvent } from '@primevue/forms'

import { useAuthStore } from '@/stores/auth'
import type { IPostSignupRequest } from '@/lib/api/api.interfaces'
import { useRouter } from 'vue-router'
import { signUpInitialValues } from '@/utils/forms/initialValues'
import { signUpResolver } from '@/utils/forms/resolvers'
import { useInputIcon } from '@/hooks/useInputIcon'

const authStore = useAuthStore()
const router = useRouter()

const initialValues = ref(signUpInitialValues)

const resolver = ref(signUpResolver)

const formRef = ref()
const usernameRef = ref<HTMLInputElement | null>(null)
const emailRef = ref<HTMLInputElement | null>(null)

const formResponseError = ref('')

const { getCurrentInputIcon, onIconClick } = useInputIcon(
  [usernameRef, emailRef],
  formRef,
  initialValues,
  false,
)

const onFormSubmit = async ({ valid, values }: FormSubmitEvent) => {
  if (!valid) return

  const data: IPostSignupRequest = {
    email: initialValues.value.email,
    password: initialValues.value.password,
  }

  if (values.username) data.full_name = initialValues.value.username

  try {
    await authStore.signUp(data)

    router.push({ name: 'email-check' })
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
  gap: 24px;
}
.inputs {
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.input-wrapper {
  display: flex;
  flex-direction: column;
  gap: 7px;
}
</style>
