import { d as defineEventHandler, a as readMultipartFormData, c as createError, u as useRuntimeConfig } from '../../nitro/nitro.mjs';
import 'node:http';
import 'node:https';
import 'node:events';
import 'node:buffer';
import 'node:fs';
import 'node:path';
import 'node:crypto';

const upload_post = defineEventHandler(async (event) => {
  const config = useRuntimeConfig();
  const parts = await readMultipartFormData(event);
  const filePart = parts == null ? void 0 : parts.find((part) => part.name === "file" && part.data);
  if (!(filePart == null ? void 0 : filePart.data) || !filePart.filename) {
    throw createError({
      statusCode: 400,
      statusMessage: "A PDF file is required."
    });
  }
  const formData = new FormData();
  formData.append(
    "file",
    new Blob([filePart.data], { type: filePart.type || "application/pdf" }),
    filePart.filename
  );
  const response = await fetch(`${config.backendApiUrl}/upload`, {
    method: "POST",
    body: formData
  });
  if (!response.ok) {
    const detail = await response.text();
    throw createError({
      statusCode: response.status,
      statusMessage: detail || "Upload failed."
    });
  }
  return await response.json();
});

export { upload_post as default };
//# sourceMappingURL=upload.post.mjs.map
