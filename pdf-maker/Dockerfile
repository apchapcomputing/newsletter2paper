# Multi-stage build: Go builder + wkhtmltopdf runtime
FROM golang:1.22-bookworm AS builder

WORKDIR /build

# Copy go module files and download dependencies
COPY go.mod go.sum ./
RUN go mod download

# Copy source code
COPY . .

# Build the PDF generator binary
RUN CGO_ENABLED=0 GOOS=linux go build -o /build/makepdf ./cmd/makepdf

# Runtime stage with wkhtmltopdf
FROM debian:bookworm-slim

# Install wkhtmltopdf and dependencies
RUN apt-get update && apt-get install -y \
    wkhtmltopdf \
    xvfb \
    fonts-dejavu-core \
    fonts-liberation \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy binary from builder
COPY --from=builder /build/makepdf /app/makepdf

# Copy styles directory
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
