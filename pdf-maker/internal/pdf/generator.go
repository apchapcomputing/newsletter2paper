package pdf

import (
	"context"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"time"

	art "pdf-maker/internal/article"
)

// GenerateOptions configures PDF generation behavior.
type GenerateOptions struct {
	OutputPath      string        // Full path to output PDF file
	TempHTMLPath    string        // Optional: path to save intermediate HTML (for debugging)
	KeepHTML        bool          // Whether to preserve intermediate HTML file
	Title           string        // PDF metadata title (default: "Your Articles")
	PageSize        string        // e.g., "Letter", "A4" (default: Letter)
	MarginTop       string        // e.g., "10mm"
	MarginBottom    string        // e.g., "10mm"
	MarginLeft      string        // e.g., "10mm"
	MarginRight     string        // e.g., "10mm"
	Timeout         time.Duration // wkhtmltopdf execution timeout
	WkhtmltopdfPath string        // Override binary path (default: "wkhtmltopdf")
}

// GenerateResult holds the outcome of PDF generation.
type GenerateResult struct {
	Success  bool
	PDFPath  string
	HTMLPath string
	Error    error
}

// GeneratePDF creates a PDF from multiple articles using wkhtmltopdf.
// It assembles HTML with header, TOC, and article sections, then invokes wkhtmltopdf.
func GeneratePDF(ctx context.Context, articles []*art.Article, opts GenerateOptions) GenerateResult {
	result := GenerateResult{}

	if len(articles) == 0 {
		result.Error = fmt.Errorf("no articles provided")
		return result
	}

	// Set defaults
	if opts.Title == "" {
		opts.Title = "Your Articles"
	}
	if opts.PageSize == "" {
		opts.PageSize = "Letter"
	}
	if opts.MarginTop == "" {
		opts.MarginTop = "15mm"
	}
	if opts.MarginBottom == "" {
		opts.MarginBottom = "15mm"
	}
	if opts.MarginLeft == "" {
		opts.MarginLeft = "12mm"
	}
	if opts.MarginRight == "" {
		opts.MarginRight = "12mm"
	}
	if opts.Timeout == 0 {
		opts.Timeout = 60 * time.Second
	}
	if opts.WkhtmltopdfPath == "" {
		opts.WkhtmltopdfPath = "wkhtmltopdf"
	}
	if opts.OutputPath == "" {
		timestamp := time.Now().Format("20060102-150405")
		opts.OutputPath = filepath.Join("newspapers", fmt.Sprintf("articles_%s.pdf", timestamp))
	}

	// Ensure output directory exists
	outDir := filepath.Dir(opts.OutputPath)
	if err := os.MkdirAll(outDir, 0o755); err != nil {
		result.Error = fmt.Errorf("mkdir output dir: %w", err)
		return result
	}

	// Generate combined HTML
	html, err := AssembleHTML(articles, opts.Title)
	if err != nil {
		result.Error = fmt.Errorf("assemble html: %w", err)
		return result
	}

	// Fix image paths to be absolute file:// URLs for wkhtmltopdf
	// This is necessary because wkhtmltopdf needs absolute paths when HTML file
	// is in a different directory than the images
	absImagesDir, _ := filepath.Abs("images")
	html = fixImagePaths(html, absImagesDir)

	// Write HTML to temp file
	htmlPath := opts.TempHTMLPath
	if htmlPath == "" {
		htmlPath = filepath.Join(outDir, fmt.Sprintf("temp_%d.html", time.Now().UnixNano()))
	}
	if err := os.WriteFile(htmlPath, []byte(html), 0o644); err != nil {
		result.Error = fmt.Errorf("write html: %w", err)
		return result
	}
	result.HTMLPath = htmlPath

	// Invoke wkhtmltopdf with xvfb-run wrapper for proper image rendering
	absHTMLPath, _ := filepath.Abs(htmlPath)
	absPDFPath, _ := filepath.Abs(opts.OutputPath)

	// Check if xvfb-run is available (Docker environment)
	useXvfb := false
	if _, err := exec.LookPath("xvfb-run"); err == nil {
		useXvfb = true
	}

	var cmd *exec.Cmd
	args := []string{
		"--enable-local-file-access",
		"--load-error-handling", "ignore",
		"--load-media-error-handling", "ignore",
		"--no-stop-slow-scripts",
		"--disable-javascript",
		"--enable-external-links",
		"--enable-internal-links",
		"--images",
		"--page-size", opts.PageSize,
		"--margin-top", opts.MarginTop,
		"--margin-bottom", opts.MarginBottom,
		"--margin-left", opts.MarginLeft,
		"--margin-right", opts.MarginRight,
		"--title", opts.Title,
		"--print-media-type",
		absHTMLPath,
		absPDFPath,
	}

	execCtx, cancel := context.WithTimeout(ctx, opts.Timeout)
	defer cancel()

	if useXvfb {
		// Use xvfb-run wrapper for virtual display (needed for image rendering in Docker)
		xvfbArgs := append([]string{"-a", "--server-args=-screen 0 1024x768x24", opts.WkhtmltopdfPath}, args...)
		cmd = exec.CommandContext(execCtx, "xvfb-run", xvfbArgs...)
	} else {
		cmd = exec.CommandContext(execCtx, opts.WkhtmltopdfPath, args...)
	}
	output, err := cmd.CombinedOutput()
	if err != nil {
		result.Error = fmt.Errorf("wkhtmltopdf failed: %w (output: %s)", err, string(output))
		return result
	}

	// Log wkhtmltopdf output if there were warnings (even on success)
	if len(output) > 0 {
		fmt.Fprintf(os.Stderr, "wkhtmltopdf output:\n%s\n", string(output))
	}

	// Cleanup temp HTML unless requested to keep
	if !opts.KeepHTML {
		_ = os.Remove(htmlPath)
		result.HTMLPath = ""
	}

	result.Success = true
	result.PDFPath = absPDFPath
	return result
}

// fixImagePaths converts relative image paths to absolute file:// URLs.
// This is necessary for wkhtmltopdf to find images when the HTML file is in a different directory.
func fixImagePaths(htmlContent string, absImagesDir string) string {
	// Simple string replacement approach - replace relative image paths with absolute file:// URLs
	// This handles the common case where images are in "images/filename.ext"
	
	// Replace src="images/ with src="file:///absolute/path/to/images/
	htmlContent = strings.ReplaceAll(htmlContent, `src="images/`, fmt.Sprintf(`src="file://%s/`, absImagesDir))
	
	// Also handle single quotes
	htmlContent = strings.ReplaceAll(htmlContent, `src='images/`, fmt.Sprintf(`src='file://%s/`, absImagesDir))
	
	return htmlContent
}
