package media

import (
	"os"
	"path/filepath"
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
