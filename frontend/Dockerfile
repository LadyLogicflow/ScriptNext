# Build stage
FROM node:20-slim AS builder
WORKDIR /app

# Copy package files
COPY package*.json ./

# Install dependencies
RUN npm ci

# Copy source code
COPY . .

# NEXT_PUBLIC_-Variablen werden von Next.js beim Build fest in den
# Client-Bundle einkompiliert, nicht zur Laufzeit gelesen -- muessen also
# hier als ARG/ENV ankommen, nicht erst im fertigen Image gesetzt werden.
ARG NEXT_PUBLIC_API_BASE
ENV NEXT_PUBLIC_API_BASE=$NEXT_PUBLIC_API_BASE

# Build Next.js app
RUN npm run build

# Production stage
FROM node:20-slim
WORKDIR /app

# Copy package files
COPY package*.json ./

# Install production dependencies only
RUN npm ci --production

# Copy built app from builder
COPY --from=builder /app/.next ./.next

# Expose port
EXPOSE 3000

# Start Next.js
CMD ["npm", "start"]
