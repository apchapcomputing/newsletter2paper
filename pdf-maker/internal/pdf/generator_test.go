package pdf

import (
	"os"
	"path/filepath"
	"strings"
	"testing"
)

var jpegHeader = []byte{0xFF, 0xD8, 0xFF, 0xE0, 0, 0x10, 'J', 'F', 'I', 'F', 0, 1}

func figure(path string) string {
	return "#figure(\n  image(\"" + path + "\", width: 100%),\n)\n\n"
}

func TestSanitizeTypstImages(t *testing.T) {
	dir := t.TempDir()
	mislabeled := filepath.Join(dir, "a.png") // JPEG content
	garbage := filepath.Join(dir, "b.png")    // HTML content
	missing := filepath.Join(dir, "c.png")
	os.WriteFile(mislabeled, jpegHeader, 0o644)
	os.WriteFile(garbage, []byte("<html>not an image</html>"), 0o644)

	src := "before\n\n" + figure(mislabeled) + figure(garbage) + figure(missing) + "after\n"
	out, dropped := sanitizeTypstImages(src)

	if len(dropped) != 2 {
		t.Fatalf("want 2 dropped, got %v", dropped)
	}
	if strings.Contains(out, garbage) || strings.Contains(out, missing) {
		t.Errorf("bad images still referenced:\n%s", out)
	}
	fixed := filepath.Join(dir, "a.jpg")
	if !strings.Contains(out, fixed) {
		t.Errorf("mislabeled image not repointed to %s:\n%s", fixed, out)
	}
	if _, err := os.Stat(fixed); err != nil {
		t.Errorf("file not renamed: %v", err)
	}
	if !strings.Contains(out, "before") || !strings.Contains(out, "after") {
		t.Errorf("surrounding content lost:\n%s", out)
	}
}
