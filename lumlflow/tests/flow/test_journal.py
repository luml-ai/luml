import json
import os
from pathlib import Path

import pytest
from lumlflow.flow.errors import JournalCorruption
from lumlflow.flow.store.journal import Journal
from lumlflow.flow.store.models import AgentBegin, SecretRefAdded

from tests.flow.helpers import cell_accepted, transaction


@pytest.fixture
def journal(tmp_path: Path) -> Journal:
    handle = Journal(tmp_path / "journal.jsonl")
    handle.ensure()
    return handle


class TestAppendAndReplay:
    def test_round_trips_transactions(self, journal: Journal) -> None:
        written = [
            transaction(1, [cell_accepted(slug="features")]),
            transaction(
                2, [AgentBegin(actor="claude-1", label="claude")], actor="agent"
            ),
            transaction(3, [SecretRefAdded(name="API_KEY")], settled=True),
        ]
        for entry in written:
            journal.append(entry)

        assert list(journal.replay()) == written

    def test_writes_one_canonical_line_per_transaction(self, journal: Journal) -> None:
        journal.append(transaction(1))
        journal.append(transaction(2))

        lines = journal.path.read_bytes().splitlines()
        assert len(lines) == 2
        first = json.loads(lines[0])
        assert list(first) == sorted(first)

    def test_replays_nothing_from_a_missing_file(self, tmp_path: Path) -> None:
        assert list(Journal(tmp_path / "absent.jsonl").replay()) == []

    def test_since_serves_a_cursor(self, journal: Journal) -> None:
        for step in (1, 2, 3):
            journal.append(transaction(step))

        assert [entry.step for entry in journal.since(1)] == [2, 3]
        assert [entry.step for entry in journal.since(3)] == []

    def test_last_step_reads_the_tail(self, journal: Journal) -> None:
        assert journal.last_step() == 0
        journal.append(transaction(1))
        journal.append(transaction(7))
        assert journal.last_step() == 7

    def test_the_append_is_fsynced(
        self, journal: Journal, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        real_fsync = os.fsync
        synced: list[int] = []

        def recording(fd: int) -> None:
            synced.append(fd)
            real_fsync(fd)

        monkeypatch.setattr(os, "fsync", recording)
        journal.append(transaction(1))

        assert synced


class TestRepair:
    def test_leaves_a_well_terminated_journal_alone(self, journal: Journal) -> None:
        journal.append(transaction(1))
        before = journal.path.read_bytes()

        assert journal.repair() == 0
        assert journal.path.read_bytes() == before

    def test_truncates_a_torn_trailing_line(self, journal: Journal) -> None:
        journal.append(transaction(1))
        journal.append(transaction(2))
        torn = b'{"step":3,"ts":"2026-08-12T09:00:03+00:00","act'
        with journal.path.open("ab") as handle:
            handle.write(torn)

        assert journal.repair() == len(torn)
        assert [entry.step for entry in journal.replay()] == [1, 2]

    def test_truncates_a_journal_that_is_nothing_but_a_torn_line(
        self, journal: Journal
    ) -> None:
        journal.path.write_bytes(b'{"step":1,"ts":"2026')

        assert journal.repair() == 20
        assert journal.path.read_bytes() == b""
        assert list(journal.replay()) == []

    def test_repairs_an_empty_journal(self, journal: Journal) -> None:
        assert journal.repair() == 0

    def test_a_torn_line_longer_than_one_scan_chunk(self, journal: Journal) -> None:
        journal.append(transaction(1))
        with journal.path.open("ab") as handle:
            handle.write(b'{"step":2,"intent":"' + b"x" * 200_000)

        assert journal.repair() == 200_020
        assert [entry.step for entry in journal.replay()] == [1]


class TestCorruption:
    def test_an_unparseable_committed_line_is_refused(self, journal: Journal) -> None:
        journal.append(transaction(1))
        with journal.path.open("ab") as handle:
            handle.write(b'{"step":2,"nonsense":true}\n')

        with pytest.raises(JournalCorruption):
            list(journal.replay())

    def test_steps_that_go_backwards_are_refused(self, journal: Journal) -> None:
        journal.append(transaction(2))
        journal.append(transaction(1))

        with pytest.raises(JournalCorruption, match="steps backwards"):
            list(journal.replay())

    def test_repair_does_not_rescue_a_committed_corrupt_line(
        self, journal: Journal
    ) -> None:
        journal.append(transaction(1))
        with journal.path.open("ab") as handle:
            handle.write(b"garbage\n")

        assert journal.repair() == 0
        with pytest.raises(JournalCorruption):
            list(journal.replay())
