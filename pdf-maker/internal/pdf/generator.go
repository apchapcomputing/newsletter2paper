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
	"pdf-maker/internal/clean"
)

// GenerateOptions configures PDF generation behavior.
type GenerateOptions struct {
	OutputPath      string        // Full path to output PDF file
	TempHTMLPath    string        // Optional: path to save intermediate HTML/Typst (for debugging)
	KeepHTML        bool          // Whether to preserve intermediate source file (HTML or .typ)
	Title           string        // PDF metadata title (default: "Your Articles")
	LayoutType      string        // Layout type: "essay" or "newspaper" (default)
	RemoveImages    bool          // Whether to remove all images from the PDF
	PageSize        string        // e.g., "Letter", "A4" (default: Letter) — wkhtmltopdf only
	MarginTop       string        // e.g., "10mm" — wkhtmltopdf only
	MarginBottom    string        // e.g., "10mm" — wkhtmltopdf only
	MarginLeft      string        // e.g., "10mm" — wkhtmltopdf only
	MarginRight     string        // e.g., "10mm" — wkhtmltopdf only
	Timeout         time.Duration // subprocess execution timeout
	WkhtmltopdfPath string        // Override wkhtmltopdf binary path (default: "wkhtmltopdf")
	TypstPath       string        // Override typst binary path (default: "typst")
}

// GenerateResult holds the outcome of PDF generation.
type GenerateResult struct {
	Success  bool
	PDFPath  string
	HTMLPath string // path to the kept intermediate source file (.html or .typ)
	Error    error
}

// GeneratePDF creates a PDF from multiple articles.
//
// Routing:
//   - "newspaper" (default) → Typst: native 3-column layout, no column-packing
//     code required, produces well-balanced columns on every page.
//   - "essay" → wkhtmltopdf: unchanged single-column rendering path.
func GeneratePDF(ctx context.Context, articles []*art.Article, opts GenerateOptions) GenerateResult {
	layout := opts.LayoutType
	if layout == "" {
		layout = "newspaper"
	}
	if layout == "newspaper" {
		return generateTypstPDF(ctx, articles, opts)
	}
	return generateWkhtmlPDF(ctx, articles, opts)
}

// generateTypstPDF renders the newspaper layout via Typst.
func generateTypstPDF(ctx context.Context, articles []*art.Article, opts GenerateOptions) GenerateResult {
	result := GenerateResult{}

	if len(articles) == 0 {
		result.Error = fmt.Errorf("no articles provided")
		return result
	}

	if opts.Title == "" {
		opts.Title = "Your Articles"
	}
	if opts.Timeout == 0 {
		opts.Timeout = 60 * time.Second
	}
	if opts.TypstPath == "" {
		opts.TypstPath = "typst"
	}
	if opts.OutputPath == "" {
		timestamp := time.Now().Format("20060102-150405")
		opts.OutputPath = filepath.Join("newspapers", fmt.Sprintf("articles_%s.pdf", timestamp))
	}

	outDir := filepath.Dir(opts.OutputPath)
	if err := os.MkdirAll(outDir, 0o755); err != nil {
		result.Error = fmt.Errorf("mkdir output dir: %w", err)
		return result
	}

	// Assemble the .typ document
	typContent, err := AssembleTypst(articles, opts.Title)
	if err != nil {
		result.Error = fmt.Errorf("assemble typst: %w", err)
		return result
	}

	// Convert any relative image paths (images/hash.ext) to absolute paths so
	// Typst can find them regardless of where the .typ file is written.
	absImagesDir, _ := filepath.Abs("images")
	typContent = fixTypstImagePaths(typContent, absImagesDir)

	// Write .typ source to a temp file in the same directory as the output PDF
	typPath := opts.TempHTMLPath
	if typPath == "" {
		typPath = filepath.Join(outDir, fmt.Sprintf("temp_%d.typ", time.Now().UnixNano()))
	} else if !strings.HasSuffix(typPath, ".typ") {
		// Caller passed an .html debug path; honour it but use .typ extension
		typPath = strings.TrimSuffix(typPath, ".html") + ".typ"
	}
	if err := os.WriteFile(typPath, []byte(typContent), 0o644); err != nil {
		result.Error = fmt.Errorf("write typst source: %w", err)
		return result
	}
	result.HTMLPath = typPath

	absTypPath, _ := filepath.Abs(typPath)
	absPDFPath, _ := filepath.Abs(opts.OutputPath)

	execCtx, cancel := context.WithTimeout(ctx, opts.Timeout)
	defer cancel()

	// Compile loop: on "failed to decode image" errors, strip the bad image
	// from the Typst source and retry (up to 10 images).
	const maxImgRetries = 10
	var output []byte
	var compileErr error
	for i := 0; i < maxImgRetries; i++ {
		cmd := exec.CommandContext(execCtx, opts.TypstPath, "compile", "--root", "/", absTypPath, absPDFPath)
		output, compileErr = cmd.CombinedOutput()
		if compileErr == nil {
			break
		}
		outStr := string(output)
		if !strings.Contains(outStr, "failed to decode image") {
			result.Error = fmt.Errorf("typst compile failed: %w (output: %s)", compileErr, outStr)
			return result
		}
		// Extract the bad image path and remove it from source + disk.
		badPath := extractImagePathFromTypstError(outStr)
		if badPath == "" {
			result.Error = fmt.Errorf("typst compile failed: %w (output: %s)", compileErr, outStr)
			return result
		}
		fmt.Fprintf(os.Stderr, "⚠️  skipping undecodable image: %s\n", badPath)
		_ = os.Remove(badPath)
		typContent = stripBadImage(typContent, badPath)
		if writeErr := os.WriteFile(typPath, []byte(typContent), 0o644); writeErr != nil {
			result.Error = fmt.Errorf("rewrite typst after removing bad image: %w", writeErr)
			return result
		}
	}
	if compileErr != nil {
		result.Error = fmt.Errorf("typst compile failed after %d retries: %w (output: %s)", maxImgRetries, compileErr, string(output))
		return result
	}
	if len(output) > 0 {
		fmt.Fprintf(os.Stderr, "typst output:\n%s\n", string(output))
	}

	if !opts.KeepHTML {
		_ = os.Remove(typPath)
		result.HTMLPath = ""
	}

	result.Success = true
	result.PDFPath = absPDFPath
	return result
}

// generateWkhtmlPDF renders the essay layout via wkhtmltopdf (unchanged path).
func generateWkhtmlPDF(ctx context.Context, articles []*art.Article, opts GenerateOptions) GenerateResult {
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
	html, err := AssembleHTML(articles, opts.Title, opts.LayoutType)
	if err != nil {
		result.Error = fmt.Errorf("assemble html: %w", err)
		return result
	}

	// Remove images if requested
	if opts.RemoveImages {
		cleanedHTML, imagesRemoved, err := clean.RemoveAllImages(html)
		if err != nil {
			result.Error = fmt.Errorf("remove images: %w", err)
			return result
		}
		html = cleanedHTML
		if imagesRemoved > 0 {
			fmt.Fprintf(os.Stderr, "Removed %d images from HTML\n", imagesRemoved)
		}
	}

	// Fix image paths to be absolute file:// URLs for wkhtmltopdf (skip if images removed)
	// This is necessary because wkhtmltopdf needs absolute paths when HTML file
	// is in a different directory than the images
	if !opts.RemoveImages {
		absImagesDir, _ := filepath.Abs("images")
		html = fixImagePaths(html, absImagesDir)
	}

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

	// Newspaper layout requires landscape orientation.
	// The CSS @page rule should handle this, but wkhtmltopdf's CLI flag is
	// more reliable than the CSS @page size directive.
	if opts.LayoutType == "newspaper" || opts.LayoutType == "" {
		args = append([]string{"--orientation", "Landscape"}, args...)
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

// extractImagePathFromTypstError parses a Typst "failed to decode image" error
// and returns the local file path that caused the failure.
func extractImagePathFromTypstError(output string) string {
	const prefix = `image("`
	idx := strings.Index(output, prefix)
	if idx < 0 {
		return ""
	}
	start := idx + len(prefix)
	end := strings.Index(output[start:], `"`)
	if end < 0 {
		return ""
	}
	return output[start : start+end]
}

// stripBadImage removes the #figure(...) block that references the given image
// path from the Typst source content, so compilation can be retried without it.
func stripBadImage(typContent, imagePath string) string {
	// Locate the image() call
	searchFor := fmt.Sprintf("image(%q, width: 100%%),", imagePath)
	idx := strings.Index(typContent, searchFor)
	if idx < 0 {
		return typContent
	}
	// Walk back to the start of the enclosing #figure(
	figStart := strings.LastIndex(typContent[:idx], "#figure(")
	if figStart < 0 {
		return typContent
	}
	// Walk forward to the closing )\n\n that ends the figure block
	closeEnd := strings.Index(typContent[figStart:], ")\n\n")
	if closeEnd < 0 {
		return typContent
	}
	closeEnd = figStart + closeEnd + len(")\n\n")
	return typContent[:figStart] + typContent[closeEnd:]
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

// fixTypstImagePaths rewrites relative "images/..." paths inside #image(...) calls to absolute
// paths so Typst can find them regardless of where the .typ source file is written.
func fixTypstImagePaths(typContent, absImagesDir string) string {
	return strings.ReplaceAll(typContent, `image("images/`, fmt.Sprintf(`image("%s/`, absImagesDir))
}
