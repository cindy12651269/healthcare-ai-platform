# Build stage
FROM node:20-alpine AS build
WORKDIR /ui
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
# Public (browser-visible) API base URL is inlined at build time. Never pass secrets here.
ARG NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
ENV NEXT_PUBLIC_API_BASE_URL=$NEXT_PUBLIC_API_BASE_URL
ENV NEXT_TELEMETRY_DISABLED=1
RUN npm run build

# Runtime stage
FROM node:20-alpine
WORKDIR /ui
ENV NODE_ENV=production
ENV HOSTNAME=0.0.0.0
ENV PORT=3000
ENV NEXT_TELEMETRY_DISABLED=1
COPY --from=build /ui/.next/standalone ./
COPY --from=build /ui/.next/static ./.next/static
EXPOSE 3000
CMD ["node", "server.js"]
