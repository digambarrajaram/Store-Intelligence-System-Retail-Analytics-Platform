# Stage 1 — build the React app
FROM node:18-alpine AS builder

WORKDIR /app

# Copy package.json only (no package-lock.json required)
COPY package.json ./

# Install all dependencies including devDependencies (tailwind, postcss, etc.)
# --legacy-peer-deps handles any peer dependency conflicts
RUN npm install --include=dev --legacy-peer-deps

# Explicitly install tailwind and postcss in case they're missing from package.json
RUN npm install tailwindcss autoprefixer postcss --save-dev --legacy-peer-deps

COPY . .

# Build — Vite outputs to /app/dist, CRA outputs to /app/build
# This handles both cases
RUN npm run build && \
    if [ -d "dist" ]; then cp -r dist /app/output; \
    elif [ -d "build" ]; then cp -r build /app/output; \
    else echo "ERROR: No build output found" && exit 1; fi

# Stage 2 — serve with nginx
FROM nginx:alpine

# Install curl for healthcheck
RUN apk add --no-cache curl

# Copy built files from builder stage
COPY --from=builder /app/output /usr/share/nginx/html

# Copy nginx config
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 3000

CMD ["nginx", "-g", "daemon off;"]