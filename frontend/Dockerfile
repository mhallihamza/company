FROM node:24-alpine AS build
WORKDIR /app

COPY frontend/package.json frontend/package-lock.json* ./

ARG NEXT_PUBLIC_API_URL=http://localhost:8700
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL

RUN npm ci --no-audit --no-fund

COPY frontend/ ./
RUN npm run build

FROM node:24-alpine
WORKDIR /app
ENV NODE_ENV=production NEXT_TELEMETRY_DISABLED=1

COPY --from=build /app ./

EXPOSE 3000
CMD ["npm", "start"]
