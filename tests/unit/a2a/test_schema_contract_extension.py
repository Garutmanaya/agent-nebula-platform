"""A2A Schema Contract Draft 0.1 Agent Card advertisement tests."""
from a2a.types import AgentCapabilities, AgentCard, AgentInterface
from google.protobuf.json_format import MessageToDict
from agent_nebula_platform.protocols.a2a.extensions.schema_contract import A2A_SCHEMA_CONTRACT_EXTENSION_URI, ensure_schema_contract_extension

class _Skill:
    skill_id = "parking.search"
    schema_contract_id = "https://agentnebula.ai/contracts/parking/search/v1"
    input_schema = {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "properties": {"airport": {"type": "string"}}, "required": ["airport"], "additionalProperties": False}
    output_schema = None

def _card():
    return AgentCard(name="test", description="test", version="1.0.0", supported_interfaces=[AgentInterface(url="https://test.example/a2a", protocol_binding="JSONRPC", protocol_version="1.0")], capabilities=AgentCapabilities(), default_input_modes=["application/json"], default_output_modes=["application/json"], skills=[])

def test_schema_contract_uses_only_official_agent_extension():
    card = _card(); ensure_schema_contract_extension(card, (_Skill(),))
    extension = next(item for item in card.capabilities.extensions if item.uri == A2A_SCHEMA_CONTRACT_EXTENSION_URI)
    assert extension.required is False
    contract = MessageToDict(extension.params)["catalog"]["inline"]["contracts"][0]
    assert contract["id"] == _Skill.schema_contract_id
    assert contract["skillIds"] == ["parking.search"]
    assert contract["input"]["presence"] == "required"
    representation = contract["input"]["representations"][0]
    assert representation["mediaType"] == "application/json"
    assert representation["schema"]["dialect"] == "https://json-schema.org/draft/2020-12/schema"
    assert representation["schema"]["inline"] == _Skill.input_schema
    assert contract["output"] == {"presence": "none"}

def test_no_contracts_does_not_advertise_extension():
    class PlainSkill:
        skill_id="hello"; schema_contract_id=None; input_schema=None; output_schema=None
    card=_card(); ensure_schema_contract_extension(card,(PlainSkill(),))
    assert all(item.uri != A2A_SCHEMA_CONTRACT_EXTENSION_URI for item in card.capabilities.extensions)
