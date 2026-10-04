package media

import (
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"sync/atomic"
	"testing"
)

var (
	jpeg = []byte{0xFF, 0xD8, 0xFF, 0xE0, 0, 0x10, 'J', 'F', 'I', 'F', 0, 1}
	avif = []byte{0, 0, 0, 0x1c, 'f', 't', 'y', 'p', 'a', 'v', 'i', 'f'}
)

func write(t *testing.T, path string, b []byte) {
	t.Helper()
	if err := os.WriteFile(path, b, 0o644); err != nil {
		t.Fatal(err)
	}
}

func TestFixImageExtensionAndCacheLookup(t *testing.T) {
	dir := t.TempDir()
	orig := filepath.Join(dir, "abc.png")
	write(t, orig, jpeg)

	fixed, err := FixImageExtension(orig)
	if err != nil || fixed != filepath.Join(dir, "abc.jpg") {
		t.Fatalf("got %q, %v", fixed, err)
	}
	// Next run looks up the URL-derived .png name; it must still hit the cache.
	if got := findCachedImage(dir, "abc", orig); got != fixed {
		t.Errorf("cache miss after rename: got %q want %q", got, fixed)
	}
	if got := findCachedImage(dir, "zzz", filepath.Join(dir, "zzz.png")); got != "" {
		t.Errorf("unexpected hit %q", got)
	}
}

func TestValidateImageFile(t *testing.T) {
	dir := t.TempDir()
	good, html, av := filepath.Join(dir, "a"), filepath.Join(dir, "b"), filepath.Join(dir, "c")
	write(t, good, jpeg)
	write(t, html, []byte("<html>nope</html>"))
	write(t, av, avif)
	if err := validateImageFile(good); err != nil {
		t.Errorf("jpeg rejected: %v", err)
	}
	if validateImageFile(html) == nil || validateImageFile(av) == nil {
		t.Error("html/avif should be rejected")
	}
}

var (
	pngBytes  = []byte("\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR")
	jpegBytes = []byte{0xFF, 0xD8, 0xFF, 0xE0, 0, 0x10, 'J', 'F', 'I', 'F'}
)

func imageServer(t *testing.T, hits *int32) *httptest.Server {
	t.Helper()
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		atomic.AddInt32(hits, 1)
		switch r.URL.Path {
		case "/ok.png":
			_, _ = w.Write(pngBytes)
		case "/ok.jpg":
			_, _ = w.Write(jpegBytes)
		case "/gone.png":
			w.WriteHeader(http.StatusNotFound)
		case "/soft-error.png": // CDNs often answer 200 with an HTML error page
			_, _ = w.Write([]byte("<html><body>Access denied</body></html>"))
		case "/tiny.png":
			_, _ = w.Write([]byte("ab"))
		default:
			w.WriteHeader(http.StatusInternalServerError)
		}
	}))
	t.Cleanup(srv.Close)
	return srv
}

func TestDownloadAndCacheImages_RewritesSrcToLocalFileAndDropsSrcset(t *testing.T) {
	var hits int32
	srv := imageServer(t, &hits)
	dir := filepath.Join(t.TempDir(), "images")
	html := `<p>Text</p><picture><source srcset="` + srv.URL + `/ok.png 2x"><img src="` + srv.URL + `/ok.png" srcset="` + srv.URL + `/ok.png 2x"></picture>`

	out, stats, err := DownloadAndCacheImages(html, DownloadOptions{ImagesDir: dir})
	if err != nil {
		t.Fatal(err)
	}

	if stats.TotalImages != 1 || stats.Downloaded != 1 || stats.Failed != 0 {
		t.Errorf("stats = %+v", stats)
	}
	if strings.Contains(out, srv.URL) || strings.Contains(out, "srcset") {
		t.Errorf("remote references must be gone (they would be fetched at render time):\n%s", out)
	}
	entries, _ := os.ReadDir(dir)
	if len(entries) != 1 || !strings.HasSuffix(entries[0].Name(), ".png") {
		t.Fatalf("expected one cached .png, got %v", entries)
	}
	if !strings.Contains(out, filepath.Join(dir, entries[0].Name())) {
		t.Errorf("src not rewritten to the cached file:\n%s", out)
	}
	if !strings.Contains(out, "Text") {
		t.Errorf("surrounding text lost:\n%s", out)
	}
}

func TestDownloadAndCacheImages_SecondRunUsesTheCacheAndMakesNoRequests(t *testing.T) {
	var hits int32
	srv := imageServer(t, &hits)
	opts := DownloadOptions{ImagesDir: filepath.Join(t.TempDir(), "images")}
	html := `<img src="` + srv.URL + `/ok.png">`

	if _, _, err := DownloadAndCacheImages(html, opts); err != nil {
		t.Fatal(err)
	}
	_, stats, err := DownloadAndCacheImages(html, opts)
	if err != nil {
		t.Fatal(err)
	}

	if stats.Cached != 1 || stats.Downloaded != 0 {
		t.Errorf("stats = %+v", stats)
	}
	if atomic.LoadInt32(&hits) != 1 {
		t.Errorf("server hit %d times, want 1", hits)
	}
}

// A broken image must not take the article with it: the <img> is removed, the failure is
// reported, and nothing unusable is left in the cache directory for Typst to choke on.
func TestDownloadAndCacheImages_FailedImagesAreRemovedAndReported(t *testing.T) {
	var hits int32
	srv := imageServer(t, &hits)
	dir := filepath.Join(t.TempDir(), "images")
	bad := []string{"/gone.png", "/soft-error.png", "/tiny.png", "/boom.png"}
	html := `<p>keep me</p>`
	for _, b := range bad {
		html += `<img src="` + srv.URL + b + `">`
	}
	html += `<img src="` + srv.URL + `/ok.jpg">`

	out, stats, err := DownloadAndCacheImages(html, DownloadOptions{ImagesDir: dir})
	if err != nil {
		t.Fatal(err)
	}

	if stats.TotalImages != 5 || stats.Downloaded != 1 || stats.Failed != 4 || len(stats.FailedURLs) != 4 {
		t.Errorf("stats = %+v", stats)
	}
	if strings.Count(out, "<img") != 1 || !strings.Contains(out, "keep me") {
		t.Errorf("only the good image and the text should remain:\n%s", out)
	}
	entries, _ := os.ReadDir(dir)
	if len(entries) != 1 {
		t.Errorf("invalid downloads must be deleted from the cache, found %d files", len(entries))
	}
}

func TestDownloadAndCacheImages_NoImagesReturnsContentWithoutTouchingDisk(t *testing.T) {
	dir := filepath.Join(t.TempDir(), "never-created")

	out, stats, err := DownloadAndCacheImages(`<p>just text</p>`, DownloadOptions{ImagesDir: dir})

	if err != nil || stats.TotalImages != 0 || !strings.Contains(out, "just text") {
		t.Fatalf("out=%q stats=%+v err=%v", out, stats, err)
	}
	if _, err := os.Stat(dir); !os.IsNotExist(err) {
		t.Error("images dir should not be created when there is nothing to download")
	}
}

func TestDownloader_ProcessHTMLAndCleanup(t *testing.T) {
	var hits int32
	srv := imageServer(t, &hits)
	dir := filepath.Join(t.TempDir(), "images")
	d, err := NewDownloader(dir)
	if err != nil {
		t.Fatal(err)
	}

	out, err := d.ProcessHTML(`<img src="` + srv.URL + `/ok.png">`)
	if err != nil || strings.Contains(out, srv.URL) {
		t.Fatalf("out=%q err=%v", out, err)
	}
	if err := d.Cleanup(); err != nil {
		t.Fatal(err)
	}
	if _, err := os.Stat(dir); !os.IsNotExist(err) {
		t.Error("Cleanup should remove the images directory")
	}
}

func TestGetImageExtension(t *testing.T) {
	cases := map[string]string{
		"https://e.com/a.png":                                        "png",
		"https://e.com/a.JPEG":                                       "jpeg",
		"https://e.com/a.webp?width=800":                             "webp",
		"https://e.com/path.with.dots/a.gif":                         "gif",
		"https://cdn.com/image/fetch/w_1456/https%3A%2F%2Fx.com%2Fa": "jpg", // extensionless CDN URL
		"https://e.com/a.php":                                        "jpg", // not an image extension
		"://bad url":                                                 "jpg",
	}
	for in, want := range cases {
		if got := getImageExtension(in); got != want {
			t.Errorf("getImageExtension(%q) = %q, want %q", in, got, want)
		}
	}
}

func TestValidateImageFile_Formats(t *testing.T) {
	cases := map[string]struct {
		data  []byte
		valid bool
	}{
		"png":                        {pngBytes, true},
		"jpeg":                       {jpegBytes, true},
		"gif":                        {[]byte("GIF89a......"), true},
		"webp":                       {[]byte("RIFF\x00\x00\x00\x00WEBPVP8 "), true},
		"avif (Typst cannot decode)": {[]byte("\x00\x00\x00\x1cftypavif"), false},
		"bmp (Typst cannot decode)":  {[]byte("BM\x00\x00\x00\x00"), false},
		"html page":                  {[]byte("<!DOCTYPE html><html>"), false},
		"json error":                 {[]byte(`{"error":"denied"}`), false},
		"too small":                  {[]byte("ab"), false},
		"empty":                      {nil, false},
		"riff but wav":               {[]byte("RIFF\x00\x00\x00\x00WAVEfmt "), false},
	}
	for name, tc := range cases {
		t.Run(name, func(t *testing.T) {
			path := filepath.Join(t.TempDir(), "f")
			if err := os.WriteFile(path, tc.data, 0o644); err != nil {
				t.Fatal(err)
			}
			if err := validateImageFile(path); (err == nil) != tc.valid {
				t.Errorf("valid=%v but err=%v", tc.valid, err)
			}
		})
	}
	if err := validateImageFile(filepath.Join(t.TempDir(), "missing")); err == nil {
		t.Error("missing file must be invalid")
	}
}
