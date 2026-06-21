"""
Redis key conventions — mirrors lib/redis/keys.ts.
"""

ENCOUNTER_ID = "demo-encounter-001"

PUBSUB_PREFIX = "nos:"


def encounter_key(encounter_id: str, suffix: str) -> str:
    return f"encounter:{encounter_id}:{suffix}"


class _EncounterKeys:
    def transcript(self, id: str) -> str:
        return encounter_key(id, "transcript")

    def buffer(self, id: str) -> str:
        return encounter_key(id, "buffer")

    def facts(self, id: str) -> str:
        return encounter_key(id, "facts")

    def timeline(self, id: str) -> str:
        return encounter_key(id, "timeline")

    def safety_flags(self, id: str) -> str:
        return encounter_key(id, "safety")

    def soap(self, id: str) -> str:
        return encounter_key(id, "soap")

    def research(self, id: str) -> str:
        return encounter_key(id, "research")

    def researched_meds(self, id: str) -> str:
        return encounter_key(id, "researched-meds")

    def handoff(self, id: str) -> str:
        return encounter_key(id, "handoff")

    def encounter_start(self, id: str) -> str:
        return encounter_key(id, "start-time")

    def symptom_timestamps(self, id: str) -> str:
        return encounter_key(id, "symptom-timestamps")

    def nremt_covered(self, id: str) -> str:
        return encounter_key(id, "nremt-covered")

    def vision_items(self, id: str) -> str:
        return encounter_key(id, "vision-items")

    def all_keys(self, id: str):
        return [
            self.transcript(id),
            self.buffer(id),
            self.facts(id),
            self.timeline(id),
            self.safety_flags(id),
            self.soap(id),
            self.research(id),
            self.researched_meds(id),
            self.handoff(id),
            self.encounter_start(id),
            self.symptom_timestamps(id),
            self.nremt_covered(id),
            self.vision_items(id),
        ]


EncounterKeys = _EncounterKeys()


def pubsub_channel(event_channel: str) -> str:
    return f"{PUBSUB_PREFIX}{event_channel}"
