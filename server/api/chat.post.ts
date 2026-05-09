import { createError, defineEventHandler, readBody } from 'h3'

export default defineEventHandler(async (event) => {
  const config = useRuntimeConfig()
  const body = await readBody<{ query?: string }>(event)

  if (!body?.query?.trim()) {
    throw createError({
      statusCode: 400,
      statusMessage: 'A query is required.'
    })
  }

  const response = await fetch(`${config.backendApiUrl}/chat`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({ query: body.query })
  })

  if (!response.ok) {
    const detail = await response.text()
    throw createError({
      statusCode: response.status,
      statusMessage: detail || 'Chat request failed.'
    })
  }

  return await response.json()
})