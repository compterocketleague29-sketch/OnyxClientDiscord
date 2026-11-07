export function safeRedirect(value: string | undefined, fallback = '/compte') {
  if (!value || !value.startsWith('/') || value.startsWith('//')) return fallback
  return value
}
