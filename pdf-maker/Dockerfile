# Multi-stage build: Go builder + Typst runtime
FROM golang:1.22-bookworm AS builder

WORKDIR /build

# Copy go module files and download dependencies
COPY go.mod go.sum ./
RUN go mod download

# Copy source code
COPY . .

# Build the PDF generator binary
RUN CGO_ENABLED=0 GOOS=linux go build -o /build/makepdf ./cmd/makepdf

# Download Typst static binary (single self-contained executable, no X11/xvfb needed)
FROM debian:bookworm-slim AS typst-downloader
RUN apt-get update && apt-get install -y curl tar xz-utils ca-certificates && rm -rf /var/lib/apt/lists/*
ARG TYPST_VERSION=v0.14.2
RUN curl -fsSL "https://github.com/typst/typst/releases/download/${TYPST_VERSION}/typst-x86_64-unknown-linux-musl.tar.xz" \
    | tar -xJ --strip-components=1 -C /usr/local/bin typst-x86_64-unknown-linux-musl/typst

# Download Typst preview packages needed at compile time
FROM debian:bookworm-slim AS typst-packages
RUN apt-get update && apt-get install -y curl ca-certificates && rm -rf /var/lib/apt/lists/*
ARG DROPLET_VERSION=0.3.1
RUN mkdir -p /typst-data/packages/preview/droplet/${DROPLET_VERSION} && \
    curl -fsSL "https://packages.typst.org/preview/droplet-${DROPLET_VERSION}.tar.gz" \
    | tar -xz -C /typst-data/packages/preview/droplet/${DROPLET_VERSION}

# Runtime stage with Typst
FROM debian:bookworm-slim

# Install fonts and TLS certs (no X11, no wkhtmltopdf, no xvfb)
RUN apt-get update && apt-get install -y \
    fonts-dejavu-core \
    fonts-liberation \
    fonts-linuxlibertine \
    fonts-noto-color-emoji \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy binaries from build stages
COPY --from=builder /build/makepdf /app/makepdf
COPY --from=typst-downloader /usr/local/bin/typst /usr/local/bin/typst
COPY --from=typst-packages /typst-data /usr/local/share/typst

# Tell Typst where to find pre-bundled packages
ENV TYPST_DATA_DIR=/usr/local/share/typst

# Copy styles directory (kept for essay layout which still uses wkhtmltopdf via local install)
COPY styles /app/styles

# Create output directories and shared directory
RUN mkdir -p /app/newspapers /app/articles /shared

# Run as non-root user for security
RUN useradd -m -u 1000 appuser && \
    chown -R appuser:appuser /app && \
    chown -R appuser:appuser /shared
USER appuser

# Default command: generate PDF from provided URLs
ENTRYPOINT ["/app/makepdf"]
CMD ["--help"]
