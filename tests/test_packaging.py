from chat_message_agent.version import __version__
from scripts.generate_version_info import render_version_info, version_tuple


def test_windows_version_metadata_uses_application_version():
    rendered = render_version_info(__version__)
    assert f"StringStruct('FileVersion', '{__version__}')" in rendered
    assert f"StringStruct('ProductVersion', '{__version__}')" in rendered
    assert f"chat-message-agent-v{__version__}.exe" in rendered


def test_version_tuple_is_padded_and_accepts_prerelease_suffix():
    assert version_tuple("1.2") == (1, 2, 0, 0)
    assert version_tuple("1.2.3-beta.1") == (1, 2, 3, 1)
