<script setup lang="ts">
import { computed, nextTick, ref } from 'vue'

type ChatRole = 'assistant' | 'user'

type ChatMessage = {
  id: number
  role: ChatRole
  text: string
  meta?: string
}

type FileSummary = {
  name: string
  sizeLabel: string
  typeLabel: string
  preview: string
}

const API_URL = 'http://localhost:8000'

const chatInput = ref('')
const selectedFile = ref<File | null>(null)
const fileSummary = ref<FileSummary | null>(null)
const isLoading = ref(false)
const isUploading = ref(false)
const messages = ref<ChatMessage[]>([
  {
    id: 1,
    role: 'assistant',
    text: 'Upload a document and I will act like a focused assistant for that file. Ask for summaries, key points, action items, or clarifications.',
    meta: 'Ready for a document'
  }
])
const chatFeed = ref<HTMLElement | null>(null)

const canSend = computed(() => chatInput.value.trim().length > 0 && Boolean(selectedFile.value) && !isLoading.value && !isUploading.value)

function formatBytes(bytes: number) {
  if (!bytes) return '0 B'
  const units = [ 'B', 'KB', 'MB', 'GB' ]
  const power = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1)
  const value = bytes / 1024 ** power
  return `${value.toFixed(value >= 10 || power === 0 ? 0 : 1)} ${units[ power ]}`
}

function inferTypeLabel(file: File) {
  if (file.type) return file.type
  const extension = file.name.split('.').pop()?.toLowerCase()
  return extension ? `${extension.toUpperCase()} file` : 'Unknown file type'
}

async function handleFileChange(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[ 0 ] ?? null

  selectedFile.value = file
  chatInput.value = ''

  if (!file) {
    fileSummary.value = null
    return
  }

  const summary: FileSummary = {
    name: file.name,
    sizeLabel: formatBytes(file.size),
    typeLabel: inferTypeLabel(file),
    preview: 'Uploading to server...'
  }

  fileSummary.value = summary
  isUploading.value = true

  try {
    const formData = new FormData()
    formData.append('file', file)

    const response = await fetch(`${API_URL}/upload`, {
      method: 'POST',
      body: formData
    })

    if (!response.ok) {
      throw new Error('Failed to upload file')
    }

    const data = await response.json()

    fileSummary.value = {
      name: file.name,
      sizeLabel: formatBytes(file.size),
      typeLabel: inferTypeLabel(file),
      preview: `✅ Successfully uploaded and indexed. Ready for questions!`
    }

    messages.value.push({
      id: Date.now(),
      role: 'assistant',
      text: `Document "${file.name}" has been successfully uploaded and indexed. You can now ask questions about it.`,
      meta: 'System'
    })

    await scrollToLatest()
  } catch (error) {
    fileSummary.value = {
      ...summary,
      preview: `❌ Upload failed: ${error instanceof Error ? error.message : 'Unknown error'}`
    }
    selectedFile.value = null
  } finally {
    isUploading.value = false
  }
}

const scrollToLatest = async () => {
  await nextTick()
  chatFeed.value?.scrollTo({ top: chatFeed.value.scrollHeight, behavior: 'smooth' })
}

async function sendMessage() {
  const prompt = chatInput.value.trim()
  if (!prompt || !selectedFile.value || isLoading.value) return

  messages.value.push({
    id: Date.now(),
    role: 'user',
    text: prompt,
    meta: 'You'
  })

  chatInput.value = ''
  isLoading.value = true
  await scrollToLatest()

  try {
    const response = await fetch(`${API_URL}/chat`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({ query: prompt })
    })

    if (!response.ok) {
      throw new Error('Failed to get response from API')
    }

    const data = await response.json()

    messages.value.push({
      id: Date.now() + 1,
      role: 'assistant',
      text: data.answer,
      meta: selectedFile.value?.name ?? 'Document assistant'
    })
  } catch (error) {
    messages.value.push({
      id: Date.now() + 1,
      role: 'assistant',
      text: `❌ Error: ${error instanceof Error ? error.message : 'Failed to process query'}`,
      meta: 'System'
    })
  } finally {
    isLoading.value = false
    await scrollToLatest()
  }
}
</script>

<template>
  <main class="shell">
    <NuxtRouteAnnouncer />

    <div class="backdrop backdrop-a"></div>
    <div class="backdrop backdrop-b"></div>

    <section class="workspace-grid">
      <section class="panel panel--upload">
        <div class="panel-header">
          <div>
            <p class="eyebrow">Upload</p>
            <h2>Drop in a document</h2>
          </div>
          <div class="stats-label">Local & cloud</div>
        </div>

        <div class="upload-panel">
          <label class="upload-dropzone" for="file-upload" :class="{ 'upload-dropzone--loading': isUploading }">
            <input id="file-upload" type="file" accept=".pdf" @change="handleFileChange" :disabled="isUploading" />
            <span class="upload-icon">{{ isUploading ? '⏳' : '+' }}</span>
            <span class="upload-title">{{ isUploading ? 'Uploading...' : 'Drop a PDF here or click to browse' }}</span>
            <span class="upload-subtitle">Only PDF files are supported. The document will be indexed for question
              answering.</span>
          </label>

          <div v-if="fileSummary" class="file-card">
            <div>
              <p class="file-name">{{ fileSummary.name }}</p>
              <p class="file-meta">{{ fileSummary.typeLabel }} · {{ fileSummary.sizeLabel }}</p>
            </div>
            <p class="file-preview">{{ fileSummary.preview }}</p>
          </div>

          <div v-else class="empty-state">
            Select a PDF document to unlock the conversation area and give the assistant a source of truth.
          </div>
        </div>
      </section>

      <section class="panel panel--chat">
        <div class="chat-header">
          <div>
            <p class="eyebrow">Chat window</p>
            <h2>Ask questions about the uploaded document</h2>
          </div>
          <div class="status-pill" :class="{ 'status-pill--ready': Boolean(selectedFile) }">
            {{ selectedFile ? 'Document ready' : 'Waiting for file' }}
          </div>
        </div>

        <div ref="chatFeed" class="chat-feed" :class="{ 'chat-feed--locked': !selectedFile }">
          <article v-for="message in messages" :key="message.id" class="message" :class="`message--${message.role}`">
            <p class="message-meta">{{ message.meta }}</p>
            <p class="message-text">{{ message.text }}</p>
          </article>

          <div v-if="!selectedFile" class="chat-lock">
            Upload a document to start a grounded conversation.
          </div>

          <div v-if="isLoading" class="message message--assistant">
            <p class="message-meta">Thinking...</p>
            <p class="message-text">⏳ Processing your question...</p>
          </div>
        </div>

        <form class="composer" @submit.prevent="sendMessage">
          <textarea v-model="chatInput" rows="3" placeholder="Ask something about the document..."
            :disabled="!selectedFile || isLoading || isUploading"></textarea>

          <div class="composer-actions">
            <p class="composer-hint">Connected to RAG backend API for real answers from your document.</p>
            <button class="send-button" type="submit" :disabled="!canSend">
              {{ isLoading ? 'Processing...' : 'Send message' }}
            </button>
          </div>
        </form>
      </section>
    </section>
  </main>
</template>

<style scoped>
:global(*) {
  box-sizing: border-box;
}

:global(body) {
  margin: 0;
  min-height: 100vh;
  font-family: "Avenir Next", "Segoe UI", "Helvetica Neue", sans-serif;
  background:
    radial-gradient(circle at top left, rgba(67, 97, 238, 0.24), transparent 34%),
    radial-gradient(circle at top right, rgba(46, 196, 182, 0.18), transparent 30%),
    linear-gradient(160deg, #07111f 0%, #0b1728 52%, #09101a 100%);
  color: #edf2ff;
}

:global(button),
:global(input),
:global(textarea) {
  font: inherit;
}

.shell {
  position: relative;
  min-height: 100vh;
  padding: 32px;
  overflow: hidden;
}

.backdrop {
  position: absolute;
  inset: auto;
  border-radius: 999px;
  filter: blur(12px);
  opacity: 0.9;
  pointer-events: none;
}

.backdrop-a {
  top: 90px;
  right: -60px;
  width: 280px;
  height: 280px;
  background: rgba(90, 155, 255, 0.18);
}

.backdrop-b {
  left: -80px;
  bottom: 80px;
  width: 340px;
  height: 340px;
  background: rgba(46, 196, 182, 0.16);
}

.hero-card,
.panel {
  position: relative;
  z-index: 1;
  max-width: 1240px;
  margin: 0 auto;
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 28px;
  background: rgba(9, 17, 31, 0.72);
  backdrop-filter: blur(18px);
  box-shadow: 0 24px 80px rgba(0, 0, 0, 0.35);
}

.hero-card {
  display: grid;
  grid-template-columns: 1fr;
  padding: 28px;
}

.workspace-grid {
  position: relative;
  z-index: 1;
  display: grid;
  grid-template-columns: minmax(0, 0.94fr) minmax(0, 1.06fr);
  gap: 20px;
  max-width: 1240px;
  margin: 0 auto;
}

.panel {
  padding: 24px;
  border-radius: 28px;
  backdrop-filter: blur(18px);
  box-shadow: 0 24px 80px rgba(0, 0, 0, 0.35);
}

.panel--upload,
.panel--chat {
  display: grid;
  gap: 18px;
}

.panel-header,
.chat-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
}

.hero-copy h1,
.chat-header h2 {
  margin: 0;
  line-height: 1.03;
  letter-spacing: -0.04em;
}

.hero-copy h1 {
  max-width: 12ch;
  font-size: clamp(2.5rem, 4vw, 4.9rem);
}

.chat-header h2 {
  font-size: clamp(1.4rem, 2vw, 2rem);
}

.panel-header h2 {
  margin: 0;
  font-size: clamp(1.3rem, 1.8vw, 1.75rem);
  line-height: 1.08;
  letter-spacing: -0.03em;
}

.eyebrow {
  margin: 0 0 12px;
  font-size: 0.78rem;
  text-transform: uppercase;
  letter-spacing: 0.24em;
  color: #8ab4ff;
}

.lede {
  max-width: 58ch;
  margin: 18px 0 0;
  color: rgba(229, 236, 255, 0.82);
  font-size: 1.02rem;
  line-height: 1.7;
}

.upload-panel {
  display: grid;
  gap: 16px;
  margin-top: 28px;
}

.upload-dropzone {
  display: grid;
  place-items: center;
  gap: 8px;
  padding: 28px;
  border: 1px dashed rgba(175, 195, 255, 0.38);
  border-radius: 24px;
  background: linear-gradient(180deg, rgba(22, 34, 55, 0.95), rgba(15, 23, 38, 0.92));
  text-align: center;
  cursor: pointer;
  transition: transform 0.18s ease, border-color 0.18s ease, background 0.18s ease;
}

.upload-dropzone:hover {
  transform: translateY(-1px);
  border-color: rgba(138, 180, 255, 0.8);
  background: linear-gradient(180deg, rgba(26, 39, 61, 0.97), rgba(15, 23, 38, 0.95));
}

.upload-dropzone--loading {
  opacity: 0.7;
  cursor: not-allowed;
}

.upload-dropzone input {
  display: none;
}

.upload-icon {
  display: grid;
  place-items: center;
  width: 54px;
  height: 54px;
  border-radius: 18px;
  background: linear-gradient(135deg, #7dd3fc, #7c3aed);
  color: white;
  font-size: 1.7rem;
  box-shadow: 0 12px 30px rgba(124, 58, 237, 0.35);
}

.upload-title {
  font-size: 1.1rem;
  font-weight: 700;
}

.upload-subtitle,
.file-meta,
.stats-card p,
.message-meta,
.composer-hint,
.empty-state,
.chat-lock {
  color: rgba(220, 231, 255, 0.7);
}

.file-card,
.stats-card,
.chat-shell,
.composer,
.message {
  border: 1px solid rgba(255, 255, 255, 0.1);
  background: rgba(11, 19, 34, 0.72);
}

.file-card {
  display: grid;
  gap: 12px;
  padding: 18px 20px;
  border-radius: 22px;
}

.file-name {
  margin: 0;
  font-size: 1rem;
  font-weight: 700;
}

.file-meta,
.file-preview,
.stats-card p,
.message-text,
.composer-hint {
  margin: 0;
  line-height: 1.6;
}

.file-preview {
  color: rgba(241, 245, 255, 0.92);
}

.empty-state {
  padding: 18px 20px;
  border-radius: 22px;
  background: rgba(255, 255, 255, 0.03);
}

.stats-card {
  padding: 24px;
  border-radius: 24px;
}

.stats-label {
  display: inline-flex;
  margin-bottom: 12px;
  padding: 6px 10px;
  border-radius: 999px;
  background: rgba(138, 180, 255, 0.12);
  color: #c6d7ff;
  font-size: 0.78rem;
  letter-spacing: 0.06em;
  text-transform: uppercase;
}

.stats-card strong {
  display: block;
  margin-bottom: 10px;
  font-size: 1.5rem;
  line-height: 1.1;
}

.status-pill {
  flex: none;
  padding: 10px 14px;
  border-radius: 999px;
  border: 1px solid rgba(255, 255, 255, 0.12);
  background: rgba(255, 255, 255, 0.04);
  color: rgba(227, 234, 255, 0.75);
}

.status-pill--ready {
  border-color: rgba(124, 255, 198, 0.32);
  background: rgba(35, 184, 138, 0.14);
  color: #c7ffe3;
}

.chat-feed {
  display: grid;
  gap: 14px;
  min-height: 360px;
  max-height: 42vh;
  padding: 4px;
  overflow: auto;
}

.chat-feed--locked {
  opacity: 0.94;
}

.message {
  width: min(88%, 760px);
  padding: 16px 18px;
  border-radius: 20px;
  box-shadow: 0 12px 24px rgba(0, 0, 0, 0.16);
}

.message--user {
  margin-left: auto;
  background: linear-gradient(135deg, rgba(79, 140, 255, 0.26), rgba(91, 74, 255, 0.22));
}

.message--assistant {
  background: linear-gradient(135deg, rgba(255, 255, 255, 0.06), rgba(255, 255, 255, 0.03));
}

.message-meta {
  margin-bottom: 8px;
  font-size: 0.78rem;
  text-transform: uppercase;
  letter-spacing: 0.18em;
}

.chat-lock {
  display: grid;
  place-items: center;
  min-height: 96px;
  margin: 18px 0 4px;
  border-radius: 18px;
  background: rgba(255, 255, 255, 0.03);
}


.composer {
  display: grid;
  gap: 14px;
  margin-top: 18px;
  padding: 16px;
  border-radius: 24px;
}

.composer textarea {
  width: 100%;
  resize: none;
  padding: 16px;
  border: 0;
  border-radius: 18px;
  background: rgba(255, 255, 255, 0.04);
  color: #f4f7ff;
  outline: none;
}

.composer textarea::placeholder {
  color: rgba(227, 234, 255, 0.5);
}

.composer textarea:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.composer-actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}

.composer-hint {
  font-size: 0.92rem;
}

.send-button {
  padding: 12px 18px;
  border: 0;
  border-radius: 14px;
  background: linear-gradient(135deg, #8b5cf6, #3b82f6);
  color: white;
  font-weight: 700;
  cursor: pointer;
  box-shadow: 0 14px 32px rgba(59, 130, 246, 0.28);
  transition: transform 0.16s ease, filter 0.16s ease, opacity 0.16s ease;
}

.send-button:hover:not(:disabled) {
  transform: translateY(-1px);
  filter: brightness(1.05);
}

.send-button:disabled {
  opacity: 0.45;
  cursor: not-allowed;
  box-shadow: none;
}

@media (max-width: 980px) {
  .shell {
    padding: 20px;
  }

  .workspace-grid {
    grid-template-columns: 1fr;
  }

  .hero-copy h1 {
    max-width: 14ch;
  }
}

@media (max-width: 680px) {

  .chat-header,
  .panel-header,
  .composer-actions {
    flex-direction: column;
    align-items: stretch;
  }

  .message {
    width: 100%;
  }

  .chat-feed {
    max-height: 52vh;
  }
}
</style>
