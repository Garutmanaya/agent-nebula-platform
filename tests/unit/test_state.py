from agent_nebula_platform import JsonFileStateStore, MemoryStateStore


def test_memory_state_is_copied():
    s = MemoryStateStore()
    v = {"a": 1}
    s.write("x", v)
    v["a"] = 2
    assert s.read("x") == {"a": 1}


def test_json_file_state_round_trip(tmp_path):
    s = JsonFileStateStore(tmp_path)
    s.write("onboarding", {"agent_id": "a"})
    assert s.read("onboarding") == {"agent_id": "a"}
    s.delete("onboarding")
    assert s.read("onboarding") is None
