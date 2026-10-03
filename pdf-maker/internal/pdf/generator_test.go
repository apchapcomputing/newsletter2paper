package pdf

import (
	"context"
	"os"
	"path/filepath"
	"runtime"
	"strings"
	"testing"
	"time"

	art "pdf-maker/internal/article"
	"pdf-maker/internal/clean"
)

func TestExtractImagePathFromTypstError(t *testing.T) {
	out := "error: failed to decode image (format error)\n  ┌─ /tmp/x.typ:12:3\n  │\n12 │   image(\"/app/images/abc123.jpg\", width: 100%),\n"
	if got := extractImagePathFromTypstError(out); got != "/app/images/abc123.jpg" {
		t.Errorf("got %q", got)
	}
	for _, bad := range []string{"", "error: something else", `image("unterminated`} {
		if got := extractImagePathFromTypstError(bad); got != "" {
			t.Errorf("%q -> %q, want empty", bad, got)
		}
	}
}

// stripBadImage must cooperate with the exact figure syntax HTMLToTypst emits, or the
// retry loop can never recover from an undecodable image.
func TestStripBadImage_RemovesOnlyTheFigureHTMLToTypstEmitted(t *testing.T) {
	body, err := clean.HTMLToTypst(
		`<p>Before.</p><figure><img src="/img/bad.jpg"><figcaption>cap</figcaption></figure>`+
			`<p>Middle.</p><figure><img src="/img/good.jpg"></figure><p>After.</p>`, false)
	if err != nil {
		t.Fatal(err)
	}

	got := stripBadImage(body, "/img/bad.jpg")

	if strings.Contains(got, "bad.jpg") || strings.Contains(got, "cap") {
		t.Errorf("bad figure not removed:\n%s", got)
	}
	for _, keep := range []string{"Before.", "Middle.", "After.", "/img/good.jpg"} {
		if !strings.Contains(got, keep) {
			t.Errorf("lost %q:\n%s", keep, got)
		}
	}
}

func TestStripBadImage_UnknownPathLeavesSourceUnchanged(t *testing.T) {
	src := "#figure(\n  image(\"/a.jpg\", width: 100%),\n)\n\n"
	if got := stripBadImage(src, "/other.jpg"); got != src {
		t.Errorf("source changed: %q", got)
	}
}

func TestFixTypstImagePaths(t *testing.T) {
	src := `image("images/a.jpg", width: 100%), image("/already/abs.jpg"), text images/not-an-image`
	got := fixTypstImagePaths(src, "/work/images")
	want := `image("/work/images/a.jpg", width: 100%), image("/already/abs.jpg"), text images/not-an-image`
	if got != want {
		t.Errorf("\n got: %s\nwant: %s", got, want)
	}
}

// fakeTypst writes a shell script that stands in for the typst binary. It fails with a
// "failed to decode image" error naming each path in badImages (once each, in order), then
// succeeds by writing a PDF. This exercises GeneratePDF's recovery loop without needing typst.
func fakeTypst(t *testing.T, badImages ...string) string {
	t.Helper()
	if runtime.GOOS == "windows" {
		t.Skip("shell script stub")
	}
	dir := t.TempDir()
	var script strings.Builder
	script.WriteString("#!/bin/sh\nsrc=\"$4\"; out=\"$5\"\n")
	for _, bad := range badImages {
		// Fail while the source still references the bad image.
		script.WriteString("if grep -q '" + bad + "' \"$src\"; then\n")
		script.WriteString("  echo 'error: failed to decode image'; echo '  image(\"" + bad + "\", width: 100%),'; exit 1\nfi\n")
	}
	script.WriteString("echo '%PDF-fake' > \"$out\"\n")
	path := filepath.Join(dir, "typst")
	if err := os.WriteFile(path, []byte(script.String()), 0o755); err != nil {
		t.Fatal(err)
	}
	return path
}

func sampleArticles(imgPath string) []*art.Article {
	content := "<p>Hello world.</p>"
	if imgPath != "" {
		content += `<figure><img src="` + imgPath + `"></figure><p>Tail.</p>`
	}
	return []*art.Article{{Title: "T", Author: "A", PubDate: time.Now(), Content: content}}
}

func TestGeneratePDF_NoArticlesIsAnError(t *testing.T) {
	res := GeneratePDF(context.Background(), nil, GenerateOptions{OutputPath: filepath.Join(t.TempDir(), "o.pdf")})
	if res.Success || res.Error == nil {
		t.Errorf("expected failure, got %+v", res)
	}
}

func TestGeneratePDF_SuccessWritesPDFAndRemovesSourceByDefault(t *testing.T) {
	out := filepath.Join(t.TempDir(), "o.pdf")

	res := GeneratePDF(context.Background(), sampleArticles(""), GenerateOptions{
		OutputPath: out, TypstPath: fakeTypst(t), LayoutType: "essay",
	})

	if !res.Success {
		t.Fatalf("failed: %v", res.Error)
	}
	if _, err := os.Stat(res.PDFPath); err != nil {
		t.Errorf("PDF missing: %v", err)
	}
	if res.HTMLPath != "" {
		t.Errorf("intermediate source should not be reported unless KeepHTML, got %q", res.HTMLPath)
	}
	leftovers, _ := filepath.Glob(filepath.Join(filepath.Dir(out), "temp_*.typ"))
	if len(leftovers) != 0 {
		t.Errorf("temp .typ not cleaned up: %v", leftovers)
	}
}

func TestGeneratePDF_KeepHTMLKeepsTheTypstSource(t *testing.T) {
	out := filepath.Join(t.TempDir(), "o.pdf")
	res := GeneratePDF(context.Background(), sampleArticles(""), GenerateOptions{
		OutputPath: out, TypstPath: fakeTypst(t), KeepHTML: true,
	})
	if !res.Success {
		t.Fatal(res.Error)
	}
	src, err := os.ReadFile(res.HTMLPath)
	if err != nil || !strings.Contains(string(src), "Hello world.") {
		t.Errorf("kept source missing or wrong: %v", err)
	}
}

func TestGeneratePDF_RecoversFromAnUndecodableImageByDroppingIt(t *testing.T) {
	out := filepath.Join(t.TempDir(), "o.pdf")
	bad := filepath.Join(t.TempDir(), "bad.jpg")
	if err := os.WriteFile(bad, []byte("not an image"), 0o644); err != nil {
		t.Fatal(err)
	}

	res := GeneratePDF(context.Background(), sampleArticles(bad), GenerateOptions{
		OutputPath: out, TypstPath: fakeTypst(t, bad), KeepHTML: true,
	})

	if !res.Success {
		t.Fatalf("expected recovery, got: %v", res.Error)
	}
	src, _ := os.ReadFile(res.HTMLPath)
	if strings.Contains(string(src), bad) {
		t.Errorf("bad image still referenced in final source")
	}
	if !strings.Contains(string(src), "Tail.") {
		t.Errorf("surrounding article text was lost")
	}
	if _, err := os.Stat(bad); !os.IsNotExist(err) {
		t.Errorf("undecodable image file should be deleted from disk")
	}
}

func TestGeneratePDF_OtherCompileErrorsFailImmediatelyWithTypstOutput(t *testing.T) {
	dir := t.TempDir()
	stub := filepath.Join(dir, "typst")
	if err := os.WriteFile(stub, []byte("#!/bin/sh\necho 'error: unknown variable: foo'; exit 1\n"), 0o755); err != nil {
		t.Fatal(err)
	}

	res := GeneratePDF(context.Background(), sampleArticles(""), GenerateOptions{
		OutputPath: filepath.Join(dir, "o.pdf"), TypstPath: stub,
	})

	if res.Success || res.Error == nil || !strings.Contains(res.Error.Error(), "unknown variable: foo") {
		t.Errorf("want failure carrying typst's message, got %+v", res)
	}
}

func TestGeneratePDF_MissingTypstBinaryFails(t *testing.T) {
	res := GeneratePDF(context.Background(), sampleArticles(""), GenerateOptions{
		OutputPath: filepath.Join(t.TempDir(), "o.pdf"), TypstPath: "/nonexistent/typst",
	})
	if res.Success || res.Error == nil {
		t.Errorf("expected failure, got %+v", res)
	}
}
