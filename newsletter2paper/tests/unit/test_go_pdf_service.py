"""GoPDFService is the seam between FastAPI and the Go renderer.

It writes a JSON contract to a shared volume, shells out to the Go binary, uploads the
resulting PDF and must always clean up its temp files. These tests pin the parts that
are easy to break silently: the JSON the Go side reads, the CLI flags, and cleanup.
"""
import json
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from services.go_pdf_service import GoPDFService


@pytest.fixture
def svc(tmp_path):
    with patch("services.go_pdf_service.StorageService") as storage:
        storage.return_value.upload_pdf.return_value = "https://storage/signed.pdf"
        service = GoPDFService(use_docker=False, shared_dir=str(tmp_path))
        service.storage = storage.return_value
        yield service


class TestPrepareArticleJson:
    def test_issue_level_fields_have_safe_defaults(self, svc):
        payload = svc._prepare_article_json([], {}, "essay")
        assert payload == {"issue_id": "", "issue_title": "Newsletter Digest",
                           "issue_description": "", "articles": [], "layout_type": "essay"}

    def test_none_values_are_dropped_but_false_is_kept(self, svc):
        # remove_images=False must reach Go explicitly; a missing key and False differ for per-article overrides.
        (article,) = svc._prepare_article_json([{"title": "T", "remove_images": False}], {})["articles"]
        assert article == {"title": "T", "remove_images": False}

    def test_untitled_fallback(self, svc):
        (article,) = svc._prepare_article_json([{}], {})["articles"]
        assert article["title"] == "Untitled"

    def test_publication_prefers_title_then_publisher(self, svc):
        arts = [{"publication_title": "Title", "publication_publisher": "Pub"},
                {"publication_publisher": "Pub"}]
        out = svc._prepare_article_json(arts, {})["articles"]
        assert [a["publication"] for a in out] == ["Title", "Pub"]


class TestExecuteGoCli:
    def run(self, svc, **kwargs):
        with patch("services.go_pdf_service.subprocess.run") as run:
            run.return_value = subprocess.CompletedProcess([], 0, "", "")
            svc._execute_go_cli(Path("in.json"), Path("out.pdf"), **kwargs)
            return run.call_args.args[0], run.call_args.kwargs

    def test_local_mode_calls_the_binary_directly(self, svc):
        cmd, kwargs = self.run(svc)
        assert cmd[0] == "/app/makepdf"
        assert cmd[cmd.index("--articles-json") + 1] == "in.json"
        assert cmd[cmd.index("--output") + 1] == "out.pdf"
        assert kwargs["timeout"] == 120 and kwargs["check"] is False

    def test_docker_mode_execs_as_root_in_the_named_container(self, svc):
        svc.use_docker = True
        svc.go_container_name = "pdf-maker-test"
        cmd, _ = self.run(svc)
        assert cmd[:6] == ["docker", "exec", "--user", "root", "pdf-maker-test", "/app/makepdf"]

    @pytest.mark.parametrize("kwargs, expected", [
        ({}, False),
        ({"remove_images": True}, True),
        # per-article flags take precedence over the global flag, so it must not be passed
        ({"remove_images": True, "has_per_article_settings": True}, False),
    ])
    def test_global_remove_images_flag(self, svc, kwargs, expected):
        cmd, _ = self.run(svc, **kwargs)
        assert ("--remove-images" in cmd) is expected

    def test_keep_html_flag(self, svc):
        assert "--keep-html" in self.run(svc, keep_html=True)[0]
        assert "--keep-html" not in self.run(svc)[0]

    def test_timeout_becomes_timeout_error(self, svc):
        with patch("services.go_pdf_service.subprocess.run", side_effect=subprocess.TimeoutExpired("x", 5)):
            with pytest.raises(TimeoutError, match="timed out after 7 seconds"):
                svc._execute_go_cli(Path("a"), Path("b"), timeout=7)

    def test_missing_binary_becomes_runtime_error(self, svc):
        with patch("services.go_pdf_service.subprocess.run", side_effect=FileNotFoundError("makepdf")):
            with pytest.raises(RuntimeError, match="not available"):
                svc._execute_go_cli(Path("a"), Path("b"))


def fake_go(write_pdf=True, returncode=0, stderr=""):
    """Stand-in for subprocess.run that behaves like makepdf: reads the JSON, writes the PDF."""
    seen = {}

    def run(cmd, **_kwargs):
        out = Path(cmd[cmd.index("--output") + 1])
        seen["json_path"] = Path(cmd[cmd.index("--articles-json") + 1])
        seen["json"] = json.loads(seen["json_path"].read_text(encoding="utf-8"))
        seen["pdf_path"] = out
        if write_pdf:
            out.write_bytes(b"%PDF-1.7 fake")
        return subprocess.CompletedProcess(cmd, returncode, "", stderr)

    return run, seen


@pytest.mark.asyncio
class TestGeneratePdf:
    ARTICLES = [{"title": "Hello Ünïcode", "content_url": "https://e.com/a"}]

    async def generate(self, svc, runner, **kwargs):
        with patch("services.go_pdf_service.subprocess.run", side_effect=runner):
            return await svc.generate_pdf_from_issue("issue-1", self.ARTICLES, {"id": "issue-1", "title": "My Issue"}, **kwargs)

    async def test_empty_issue_fails_without_calling_go(self, svc):
        with patch("services.go_pdf_service.subprocess.run") as run:
            result = await svc.generate_pdf_from_issue("i", [], {})
        assert result["success"] is False and "No articles" in result["error"]
        run.assert_not_called()

    async def test_success_uploads_pdf_bytes_and_returns_url(self, svc):
        runner, seen = fake_go()

        result = await self.generate(svc, runner, layout_type="essay")

        assert result["success"] and result["pdf_url"] == "https://storage/signed.pdf"
        assert seen["json"]["layout_type"] == "essay"
        assert seen["json"]["articles"][0]["title"] == "Hello Ünïcode"  # not \u-escaped garbage
        uploaded_bytes = svc.storage.upload_pdf.call_args.args[0]
        assert uploaded_bytes == b"%PDF-1.7 fake"

    async def test_default_filename_is_sanitised_issue_title(self, svc):
        runner, _ = fake_go()
        with patch("services.go_pdf_service.subprocess.run", side_effect=runner):
            await svc.generate_pdf_from_issue("i", self.ARTICLES, {"title": "A/B: Weekly? Digest!"})
        filename = svc.storage.upload_pdf.call_args.args[1]
        assert filename.startswith("AB_Weekly_Digest_")
        assert all(c.isalnum() or c in "_-" for c in filename)

    async def test_nonzero_exit_reports_stderr_and_skips_upload(self, svc):
        runner, _ = fake_go(returncode=2, stderr="typst: boom", write_pdf=False)

        result = await self.generate(svc, runner)

        assert not result["success"]
        assert "exit code 2" in result["error"] and "typst: boom" in result["error"]
        svc.storage.upload_pdf.assert_not_called()

    async def test_exit_zero_without_a_pdf_is_still_a_failure(self, svc):
        runner, _ = fake_go(write_pdf=False)
        result = await self.generate(svc, runner)
        assert not result["success"] and "not created" in result["error"]

    async def test_upload_failure_is_reported_not_raised(self, svc):
        svc.storage.upload_pdf.side_effect = RuntimeError("bucket down")
        runner, _ = fake_go()
        result = await self.generate(svc, runner)
        assert not result["success"] and "bucket down" in result["error"]

    async def test_timeout_is_reported(self, svc):
        with patch("services.go_pdf_service.subprocess.run", side_effect=subprocess.TimeoutExpired("x", 1)):
            result = await svc.generate_pdf_from_issue("i", self.ARTICLES, {}, timeout=1)
        assert not result["success"] and "timed out" in result["error"]

    @pytest.mark.parametrize("scenario", ["ok", "go_fails", "upload_fails"])
    async def test_temp_files_are_always_removed(self, svc, scenario):
        runner, seen = fake_go(returncode=1 if scenario == "go_fails" else 0)
        if scenario == "upload_fails":
            svc.storage.upload_pdf.side_effect = RuntimeError("x")

        await self.generate(svc, runner)

        assert not seen["json_path"].exists() and not seen["pdf_path"].exists()
