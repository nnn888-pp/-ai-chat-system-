const SALT = 'chat-system-static-salt'

/**
 * 与后端 SHA256_SALT 保持一致：前端先 sha256(明文 + 盐)，
 * 后端再对该十六进制串做 bcrypt 入库，避免明文出网。
 */
export async function sha256Hex(text) {
  const buf = new TextEncoder().encode(text)
  const digest = await crypto.subtle.digest('SHA-256', buf)
  return Array.from(new Uint8Array(digest))
    .map((b) => b.toString(16).padStart(2, '0'))
    .join('')
}

export function hashPassword(plain) {
  return sha256Hex(plain + SALT)
}
