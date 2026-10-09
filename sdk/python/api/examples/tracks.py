"""Tracks: versioning one model and marking which version serves where.

A track groups the versions of one model. Every artifact added to it becomes
the next version, and stages (for example ``dev``, ``staging``,
``production``) hold at most one version each, so "what is in production" is
always one lookup away.
"""

from luml_api import ArtifactType, LumlClient, SortOrder
from luml_api._types import StageUpsertIn, TrackEntrySortBy, TrackSortBy

ORGANIZATION_ID = "0199c455-21ec-7c74-8efe-41470e29bae5"
ORBIT_ID = "0199c455-21ed-7aba-9fe5-5231611220de"
MODEL_V1_ID = "0199c455-21ee-74c6-b747-19a82f1a1e82"
MODEL_V2_ID = "0199c455-21ee-74c6-b747-19a82f1a1e84"

luml = LumlClient(
    api_key="luml_your_api_key_here",
    organization=ORGANIZATION_ID,
    orbit=ORBIT_ID,
)


def main() -> None:
    # A track for one model, with its stages created up front
    track = luml.tracks.create(
        name="churn-model",
        artifact_type=ArtifactType.MODEL,
        description="Customer churn predictor",
        tags=["churn"],
        stages=["dev", "staging", "production"],
    )
    track_id = str(track.id)
    print(f"Created track: {track}")

    # Tracks of the orbit, one page at a time, filtered and sorted
    page = luml.tracks.list(
        types=[ArtifactType.MODEL],
        tags=["churn"],
        sort_by=TrackSortBy.NAME,
        order=SortOrder.ASC,
        limit=50,
    )
    print(f"Tracks: {page.items}, next page from: {page.cursor}")

    # Every tag used by the orbit's tracks
    tags = luml.tracks.list_tags()
    print(f"Track tags: {tags}")

    # One track, with its stages and version counters
    fetched = luml.tracks.get(track_id)
    print(f"Track: {fetched}")

    # Stages are upserted: an entry with an id renames that stage, an entry
    # without one adds a stage. Stages left out are kept as they are
    renamed = next(stage for stage in track.stages if stage.name == "production")
    track = luml.tracks.update(
        track_id,
        description="Customer churn predictor, retrained monthly",
        stages=[
            StageUpsertIn(id=renamed.id, name="prod"),
            StageUpsertIn(name="canary"),
        ],
    )
    stages = luml.tracks.list_stages(track_id)
    print(f"Stages: {[(stage.name, stage.is_used) for stage in stages]}")

    # Versions: every artifact added becomes the next version. A stage can be
    # given right away
    v1 = luml.tracks.add_artifact(track_id, MODEL_V1_ID)
    v2 = luml.tracks.add_artifact(track_id, MODEL_V2_ID, stage="dev")
    print(f"Added v{v1.version} and v{v2.version} ({v2.stage_name})")

    # The versions, newest first, and the ones in one stage
    versions = luml.tracks.list_artifacts(
        track_id, sort_by=TrackEntrySortBy.VERSION, order=SortOrder.DESC
    )
    print(f"Versions: {versions.items}")

    in_dev = luml.tracks.list_artifacts(track_id, stage="dev")
    print(f"In dev: {in_dev.items}")

    # One version by its entry id, or the version a stage holds right now
    entry = luml.tracks.get_artifact(track_id, str(v2.id))
    print(f"Entry: {entry}")

    serving = luml.tracks.get_artifact_by_stage(track_id, "prod")
    print(f"In production: v{serving.version} ({serving.artifact_name})")

    # Promotion. A stage holds one version, so moving into an occupied stage
    # needs force=True, which takes the current occupant out of the stage
    luml.tracks.update_artifact(track_id, str(v2.id), stage="staging")
    luml.tracks.update_artifact(track_id, str(v2.id), stage="prod", force=True)

    # Take a version out of every stage without removing it from the track
    luml.tracks.update_artifact(track_id, str(v1.id), stage=None)

    # Remove versions from the track; the artifacts themselves stay
    luml.tracks.remove_artifact(track_id, str(v1.id))
    luml.tracks.remove_batch_artifacts(track_id, [str(v2.id)])

    # Delete the track
    luml.tracks.delete(track_id)


if __name__ == "__main__":
    main()
