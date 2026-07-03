"""Pilot tests for the Attachments tab.

Covers SPEC.md task: "Build the attachments tab" — the file/folder
tree with sizes, inline preview of text-like files, best-effort image
rendering with save-to-disk fallback, large-file guard, and the
save-to-disk action.

All tests use Textual's headless `App.run_test()` + `Pilot` against an
in-memory seeded `ExperimentTracker` so the suite is deterministic
and fast.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from luml.experiments.tracker import ExperimentTracker
from lumlflow.tui import LumlflowApp
from lumlflow.tui.data import DataFacade
from lumlflow.tui.screens.experiment_detail import ExperimentDetailScreen
from lumlflow.tui.widgets.attachments_panel import (
    LARGE_FILE_THRESHOLD,
    AttachmentsPanel,
    _decode_text,
    _format_size,
    _is_image,
    _is_text_like,
)
from lumlflow.tui.widgets.save_file_dialog import SaveFileDialog
from textual.widgets import Static, Tree

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def tracker(tmp_path: Path) -> ExperimentTracker:
    return ExperimentTracker(f"sqlite://{tmp_path / 'experiments'}")


@pytest.fixture
def facade(tracker: ExperimentTracker) -> DataFacade:
    return DataFacade(tracker=tracker)


def _make_app(facade: DataFacade) -> LumlflowApp:
    return LumlflowApp(facade=facade)


def _seed_experiment_with_attachments(
    tracker: ExperimentTracker,
    *,
    group: str = "g",
    name: str = "exp",
    attachments: list[tuple[str, str]] | None = None,
) -> str:
    """Seed an experiment with a few logged attachments.

    `attachments` is a list of `(name, content)` pairs; if omitted, a
    sensible default set with a nested folder, a JSON file, and an
    image is created.
    """

    tracker.create_group(group)
    exp_id = tracker.start_experiment(name=name, group=group)
    if attachments is None:
        attachments = [
            ("config.json", '{"lr": 0.001, "batch_size": 32}'),
            ("README.md", "# Experiment notes\n\nLogged from train.py"),
            ("plots/loss.svg", "<svg/>"),
            ("plots/acc.svg", "<svg>2</svg>"),
        ]
    for n, c in attachments:
        tracker.log_attachment(n, c)
    return exp_id


def _push_detail_screen(
    app: LumlflowApp,
    facade: DataFacade,
    *,
    experiment_id: str,
    experiment_name: str | None = None,
    group_name: str | None = None,
) -> ExperimentDetailScreen:
    screen = ExperimentDetailScreen(
        facade=facade,
        experiment_id=experiment_id,
        experiment_name=experiment_name,
        group_name=group_name,
    )
    app.push_screen(screen)
    return screen


async def _open_attachments_tab(
    app: LumlflowApp,
    facade: DataFacade,
    exp_id: str,
    pilot,
) -> AttachmentsPanel:
    screen = _push_detail_screen(
        app, facade, experiment_id=exp_id, experiment_name="exp"
    )
    await pilot.pause()
    await pilot.pause()
    screen.action_jump_tab("attachments")
    await pilot.pause()
    await pilot.pause()
    return screen.query_one("#pane-attachments-panel", AttachmentsPanel)


# ---------------------------------------------------------------------------
# Helper-function tests
# ---------------------------------------------------------------------------


class TestFormatSize:
    def test_none(self) -> None:
        assert _format_size(None) == "—"

    def test_bytes(self) -> None:
        assert "B" in _format_size(100)

    def test_kib(self) -> None:
        assert "KiB" in _format_size(2048)

    def test_mib(self) -> None:
        assert "MiB" in _format_size(5 * 1024 * 1024)

    def test_gib(self) -> None:
        assert "GiB" in _format_size(2 * 1024 * 1024 * 1024)


class TestIsTextLike:
    def test_txt_is_text(self) -> None:
        assert _is_text_like("notes.txt")

    def test_json_is_text(self) -> None:
        assert _is_text_like("config.json")

    def test_md_is_text(self) -> None:
        assert _is_text_like("readme.md")

    def test_csv_is_text(self) -> None:
        assert _is_text_like("results.csv")

    def test_svg_is_text(self) -> None:
        assert _is_text_like("plot.svg")

    def test_png_is_not_text(self) -> None:
        assert not _is_text_like("plot.png")

    def test_binary_is_not_text(self) -> None:
        assert not _is_text_like("model.bin")


class TestIsImage:
    def test_png_is_image(self) -> None:
        assert _is_image("plot.png")

    def test_jpg_is_image(self) -> None:
        assert _is_image("photo.jpg")

    def test_jpeg_is_image(self) -> None:
        assert _is_image("photo.jpeg")

    def test_gif_is_image(self) -> None:
        assert _is_image("anim.gif")

    def test_txt_is_not_image(self) -> None:
        assert not _is_image("notes.txt")


class TestDecodeText:
    def test_utf8_decoding(self) -> None:
        assert _decode_text(b"hello") == "hello"

    def test_invalid_bytes_use_replacement(self) -> None:
        result = _decode_text(b"\xff\xfe hello")
        # Replacement characters keep the rest readable.
        assert "hello" in result

    def test_truncation_on_large_input(self) -> None:
        big = b"x" * 300_000
        out = _decode_text(big, max_chars=1000)
        assert "truncated" in out
        assert len(out) < 2000


# ---------------------------------------------------------------------------
# Tree navigation
# ---------------------------------------------------------------------------


class TestTreeNavigation:
    async def test_tree_loads_on_tab_activation(
        self, facade: DataFacade, tracker: ExperimentTracker
    ) -> None:
        exp_id = _seed_experiment_with_attachments(tracker)
        app = _make_app(facade)
        async with app.run_test() as pilot:
            await pilot.pause()
            panel = await _open_attachments_tab(app, facade, exp_id, pilot)
            tree = panel.query_one("#attachments-tree", Tree)
            assert len(tree.root.children) > 0

    async def test_tree_shows_folders_and_files(
        self, facade: DataFacade, tracker: ExperimentTracker
    ) -> None:
        exp_id = _seed_experiment_with_attachments(tracker)
        app = _make_app(facade)
        async with app.run_test() as pilot:
            await pilot.pause()
            panel = await _open_attachments_tab(app, facade, exp_id, pilot)
            tree = panel.query_one("#attachments-tree", Tree)
            # Folders sort before files; the root's children should
            # include both a "plots" folder and the README.md file.
            labels = [str(node.label) for node in tree.root.children]
            joined = " ".join(labels)
            assert "plots" in joined
            assert "README.md" in joined
            assert "config.json" in joined

    async def test_folder_size_shown(
        self, facade: DataFacade, tracker: ExperimentTracker
    ) -> None:
        exp_id = _seed_experiment_with_attachments(tracker)
        app = _make_app(facade)
        async with app.run_test() as pilot:
            await pilot.pause()
            panel = await _open_attachments_tab(app, facade, exp_id, pilot)
            tree = panel.query_one("#attachments-tree", Tree)
            labels = [str(node.label) for node in tree.root.children]
            # At least one of the labels mentions a size unit.
            assert any(
                unit in label for label in labels for unit in ("B", "KiB", "MiB")
            )

    async def test_folder_expansion_loads_children(
        self, facade: DataFacade, tracker: ExperimentTracker
    ) -> None:
        exp_id = _seed_experiment_with_attachments(tracker)
        app = _make_app(facade)
        async with app.run_test() as pilot:
            await pilot.pause()
            panel = await _open_attachments_tab(app, facade, exp_id, pilot)
            tree = panel.query_one("#attachments-tree", Tree)
            plots_node = next(
                (n for n in tree.root.children if "plots" in str(n.label)),
                None,
            )
            assert plots_node is not None
            # The folder starts collapsed and empty; expanding triggers
            # the lazy `parent_path` fetch.
            plots_node.expand()
            await pilot.pause()
            await pilot.pause()
            await pilot.pause()
            child_labels = [str(c.label) for c in plots_node.children]
            joined = " ".join(child_labels)
            assert "loss.svg" in joined
            assert "acc.svg" in joined


# ---------------------------------------------------------------------------
# Empty state
# ---------------------------------------------------------------------------


class TestEmptyState:
    async def test_empty_attachments_shown(
        self, facade: DataFacade, tracker: ExperimentTracker
    ) -> None:
        tracker.create_group("g")
        exp_id = tracker.start_experiment(name="empty", group="g")
        app = _make_app(facade)
        async with app.run_test() as pilot:
            await pilot.pause()
            panel = await _open_attachments_tab(app, facade, exp_id, pilot)
            header = panel.query_one("#attachments-preview-header", Static)
            assert "No attachments" in str(header.render())


# ---------------------------------------------------------------------------
# Text preview
# ---------------------------------------------------------------------------


class TestTextPreview:
    async def test_json_renders_inline(
        self, facade: DataFacade, tracker: ExperimentTracker
    ) -> None:
        exp_id = _seed_experiment_with_attachments(tracker)
        app = _make_app(facade)
        async with app.run_test() as pilot:
            await pilot.pause()
            panel = await _open_attachments_tab(app, facade, exp_id, pilot)
            tree = panel.query_one("#attachments-tree", Tree)
            # Locate the JSON node.
            json_node = next(
                (n for n in tree.root.children if "config.json" in str(n.label)),
                None,
            )
            assert json_node is not None
            tree.select_node(json_node)
            await pilot.pause()
            await pilot.pause()
            await pilot.pause()
            body = panel.query_one("#attachments-preview-body", Static)
            text = str(body.render())
            assert "lr" in text or "batch_size" in text

    async def test_markdown_renders_inline(
        self, facade: DataFacade, tracker: ExperimentTracker
    ) -> None:
        exp_id = _seed_experiment_with_attachments(tracker)
        app = _make_app(facade)
        async with app.run_test() as pilot:
            await pilot.pause()
            panel = await _open_attachments_tab(app, facade, exp_id, pilot)
            tree = panel.query_one("#attachments-tree", Tree)
            md_node = next(
                (n for n in tree.root.children if "README.md" in str(n.label)),
                None,
            )
            assert md_node is not None
            tree.select_node(md_node)
            await pilot.pause()
            await pilot.pause()
            await pilot.pause()
            body = panel.query_one("#attachments-preview-body", Static)
            assert "Experiment notes" in str(body.render())


# ---------------------------------------------------------------------------
# Image preview fallback (image rendering unsupported in headless mode)
# ---------------------------------------------------------------------------


class TestImageFallback:
    async def test_image_unsupported_renders_fallback(
        self, facade: DataFacade, tracker: ExperimentTracker
    ) -> None:
        # Seed an experiment with a tiny PNG attachment so the panel
        # has an image-typed file to attempt to preview.
        png_bytes = bytes.fromhex(
            "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4"
            "890000000d49444154789c6300010000000500015e2e1c0c0000000049454e44"
            "ae426082"
        )
        tracker.create_group("g")
        exp_id = tracker.start_experiment(name="img", group="g")
        tracker.log_attachment("preview.png", png_bytes, binary=True)
        app = _make_app(facade)
        async with app.run_test() as pilot:
            await pilot.pause()
            panel = await _open_attachments_tab(app, facade, exp_id, pilot)
            tree = panel.query_one("#attachments-tree", Tree)
            png_node = next(
                (n for n in tree.root.children if "preview.png" in str(n.label)),
                None,
            )
            assert png_node is not None
            tree.select_node(png_node)
            body = panel.query_one("#attachments-preview-body", Static)
            # Wait for the preview worker to finish; the body should
            # leave "Loading…" once the bytes have arrived and the
            # image branch picks up the unsupported-terminal fallback.
            for _ in range(30):
                await pilot.pause()
                text = str(body.render())
                if text != "Loading…":
                    break
            text = str(body.render())
            # The headless test environment doesn't support an inline
            # image protocol — the panel falls back to a save-to-disk hint.
            assert "save" in text.lower() or "not supported" in text.lower()


# ---------------------------------------------------------------------------
# Large-file guard
# ---------------------------------------------------------------------------


class TestLargeFileGuard:
    async def test_large_file_not_previewed(
        self, facade: DataFacade, tracker: ExperimentTracker
    ) -> None:
        # Build an attachment that exceeds the inline-preview threshold.
        big = "x" * (LARGE_FILE_THRESHOLD + 100)
        tracker.create_group("g")
        exp_id = tracker.start_experiment(name="big", group="g")
        tracker.log_attachment("big.txt", big)
        app = _make_app(facade)
        async with app.run_test() as pilot:
            await pilot.pause()
            panel = await _open_attachments_tab(app, facade, exp_id, pilot)
            tree = panel.query_one("#attachments-tree", Tree)
            big_node = next(
                (n for n in tree.root.children if "big.txt" in str(n.label)),
                None,
            )
            assert big_node is not None
            tree.select_node(big_node)
            await pilot.pause()
            await pilot.pause()
            body = panel.query_one("#attachments-preview-body", Static)
            text = str(body.render())
            # The body should NOT contain the raw content; it should
            # state the threshold was exceeded.
            assert "x" * 100 not in text
            assert "threshold" in text.lower() or "save" in text.lower()


# ---------------------------------------------------------------------------
# Save-to-disk
# ---------------------------------------------------------------------------


class TestSaveToDisk:
    async def test_save_action_opens_dialog(
        self, facade: DataFacade, tracker: ExperimentTracker
    ) -> None:
        exp_id = _seed_experiment_with_attachments(tracker)
        app = _make_app(facade)
        async with app.run_test() as pilot:
            await pilot.pause()
            panel = await _open_attachments_tab(app, facade, exp_id, pilot)
            tree = panel.query_one("#attachments-tree", Tree)
            json_node = next(
                (n for n in tree.root.children if "config.json" in str(n.label)),
                None,
            )
            assert json_node is not None
            tree.select_node(json_node)
            await pilot.pause()
            panel.action_save_focused()
            await pilot.pause()
            assert isinstance(app.screen, SaveFileDialog)

    async def test_save_writes_bytes_to_disk(
        self,
        facade: DataFacade,
        tracker: ExperimentTracker,
        tmp_path: Path,
    ) -> None:
        exp_id = _seed_experiment_with_attachments(tracker)
        app = _make_app(facade)
        async with app.run_test() as pilot:
            await pilot.pause()
            panel = await _open_attachments_tab(app, facade, exp_id, pilot)
            tree = panel.query_one("#attachments-tree", Tree)
            json_node = next(
                (n for n in tree.root.children if "config.json" in str(n.label)),
                None,
            )
            assert json_node is not None
            tree.select_node(json_node)
            await pilot.pause()
            target = tmp_path / "saved_config.json"
            panel._on_save_dest(str(target), "config.json")
            # Wait for the worker to finish writing.
            for _ in range(20):
                await pilot.pause()
                if target.exists():
                    break
            assert target.exists()
            assert b"lr" in target.read_bytes()

    async def test_save_dialog_cancel_writes_nothing(
        self,
        facade: DataFacade,
        tracker: ExperimentTracker,
        tmp_path: Path,
    ) -> None:
        exp_id = _seed_experiment_with_attachments(tracker)
        app = _make_app(facade)
        async with app.run_test() as pilot:
            await pilot.pause()
            panel = await _open_attachments_tab(app, facade, exp_id, pilot)
            tree = panel.query_one("#attachments-tree", Tree)
            json_node = next(
                (n for n in tree.root.children if "config.json" in str(n.label)),
                None,
            )
            assert json_node is not None
            tree.select_node(json_node)
            await pilot.pause()
            target = tmp_path / "should_not_exist.json"
            # The dialog returns None on cancel; the panel should bail
            # without touching the filesystem.
            panel._on_save_dest(None, "config.json")
            await pilot.pause()
            await pilot.pause()
            assert not target.exists()


class TestSaveKeybindings:
    """`s` is the primary save key; `w` stays as a vim-style alias."""

    @pytest.mark.parametrize("key", ["s", "w"])
    async def test_key_opens_save_dialog(
        self,
        facade: DataFacade,
        tracker: ExperimentTracker,
        key: str,
    ) -> None:
        exp_id = _seed_experiment_with_attachments(tracker)
        app = _make_app(facade)
        async with app.run_test() as pilot:
            await pilot.pause()
            panel = await _open_attachments_tab(app, facade, exp_id, pilot)
            tree = panel.query_one("#attachments-tree", Tree)
            json_node = next(
                (n for n in tree.root.children if "config.json" in str(n.label)),
                None,
            )
            assert json_node is not None
            tree.select_node(json_node)
            tree.focus()
            await pilot.pause()
            await pilot.press(key)
            await pilot.pause()
            assert isinstance(app.screen, SaveFileDialog)
