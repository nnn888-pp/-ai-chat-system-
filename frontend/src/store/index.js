import { reactive } from 'vue'
import { getCachedUser, setCachedUser, setToken, clearAuth, getToken } from '../api'

export const store = reactive({
  user: getCachedUser(),
  get loggedIn() {
    return Boolean(getToken() && this.user)
  },
})

export function saveLogin(token, user) {
  setToken(token)
  setCachedUser(user)
  store.user = user
}

export function updateUser(user) {
  setCachedUser(user)
  store.user = user
}

export function logout() {
  clearAuth()
  store.user = null
}
