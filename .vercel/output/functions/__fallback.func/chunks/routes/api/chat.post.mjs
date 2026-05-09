import { d as defineEventHandler, r as readBody, c as createError, u as useRuntimeConfig } from '../../nitro/nitro.mjs';
import 'node:http';
import 'node:https';
import 'node:events';
import 'node:buffer';
import 'node:fs';
import 'node:path';
import 'node:crypto';

const chat_post = defineEventHandler(async (event) => {
  var _a;
  const config = useRuntimeConfig();
  const body = await readBody(event);
  if (!((_a = body == null ? void 0 : body.query) == null ? void 0 : _a.trim())) {
    throw createError({
      statusCode: 400,
      statusMessage: "A query is required."
    });
  }
  const response = await fetch(`${config.backendApiUrl}/chat`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify({ query: body.query })
  });
  if (!response.ok) {
    const detail = await response.text();
    throw createError({
      statusCode: response.status,
      statusMessage: detail || "Chat request failed."
    });
  }
  return await response.json();
});

export { chat_post as default };
//# sourceMappingURL=chat.post.mjs.map
