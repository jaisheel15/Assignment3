import { createError, defineEventHandler, readMultipartFormData } from 'h3'

export default defineEventHandler(async (event) => {
  const config = useRuntimeConfig()
  const parts = await readMultipartFormData(event)
  const filePart = parts?.find((part) => part.name === 'file' && part.data)

  if (!filePart?.data || !filePart.filename) {
    throw createError({
      statusCode: 400,
      statusMessage: 'A PDF file is required.'
    })
  }

  const formData = new FormData()
  formData.append(
    'file',
    new Blob([filePart.data], { type: filePart.type || 'application/pdf' }),
    filePart.filename
  )

  const response = await fetch(`${config.backendApiUrl}/upload`, {
    method: 'POST',
    body: formData
  })

  if (!response.ok) {
    const detail = await response.text()
    throw createError({
      statusCode: response.status,
      statusMessage: detail || 'Upload failed.'
    })
  }

  return await response.json()
})