# FireClip web (Next.js standalone).
FROM node:22-alpine AS deps
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci

FROM node:22-alpine AS builder
WORKDIR /app
ENV NEXT_TELEMETRY_DISABLED=1
COPY --from=deps /app/node_modules ./node_modules
COPY . .
# Rewrites are baked into the standalone output, so the API origin is a build arg.
ARG API_BASE_URL=http://api:8000
ENV API_BASE_URL=$API_BASE_URL
RUN npm run build

FROM node:22-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    PORT=3000 \
    HOSTNAME=0.0.0.0
RUN addgroup --system --gid 1001 nodejs \
    && adduser --system --uid 1001 nextjs
COPY --from=builder /app/public ./public
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static
# Startup report: which container the proxied API hostname actually reaches.
COPY --chown=nextjs:nodejs check-api.mjs docker-entrypoint.sh ./
RUN chmod +x docker-entrypoint.sh
USER nextjs
# 3000 is the default; Compose overrides PORT to match WEB_CONTAINER_PORT.
EXPOSE 3000
ENTRYPOINT ["/app/docker-entrypoint.sh"]
CMD ["node", "server.js"]
