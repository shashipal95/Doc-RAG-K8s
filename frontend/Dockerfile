# ===================================
# Stage 1 - Install dependencies
# ===================================
FROM node:20-alpine AS deps

WORKDIR /app

COPY package.json package-lock.json ./

RUN npm ci


# ===================================
# Stage 2 - Build application
# ===================================
FROM node:20-alpine AS builder

WORKDIR /app

COPY --from=deps /app/node_modules ./node_modules

COPY . .

RUN npm run build


# ===================================
# Stage 3 - Production Runtime
# ===================================
FROM node:20-alpine AS runner

WORKDIR /app

ENV NODE_ENV=production

# Create non-root user
RUN addgroup -S nextjs && \
    adduser -S nextjs -G nextjs

# Copy standalone build
COPY --from=builder /app/.next/standalone ./

# Static files
COPY --from=builder /app/.next/static ./.next/static

# Public assets
COPY --from=builder /app/public ./public

USER nextjs

EXPOSE 3000

ENV PORT=3000

CMD ["node", "server.js"]