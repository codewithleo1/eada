# ── Stage 1: build the Vite/React app ──────────────────────────────────────
FROM node:20-alpine AS builder

WORKDIR /app

# Copy package files first — cached until dependencies change
COPY frontend/package.json frontend/package-lock.json* ./

RUN npm ci

# Copy frontend source and build
COPY frontend/ ./

RUN npm run build

# ── Stage 2: serve with Nginx ───────────────────────────────────────────────
FROM nginx:alpine AS runtime

# Remove default nginx static files
RUN rm -rf /usr/share/nginx/html/*

# Copy built app from builder
COPY --from=builder /app/dist /usr/share/nginx/html

# Copy our custom nginx config (we'll create this in Step 3)
COPY infra/nginx/nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
