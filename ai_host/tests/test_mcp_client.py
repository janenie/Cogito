from types import SimpleNamespace

from mcp.types import CallToolResult, ImageContent, TextContent

from ai_host.mcp_client import result_to_image_messages, result_to_payload


def test_result_to_payload_uses_structured_content_and_text():
    result = CallToolResult(
        content=[TextContent(type="text", text="hello")],
        structuredContent={"status": "ready"},
        isError=False,
    )

    payload = result_to_payload(result)

    assert payload["status"] == "ready"
    assert payload["is_error"] is False
    assert payload["text"] == ["hello"]


def test_result_to_image_messages_translates_mcp_images():
    result = CallToolResult(
        content=[
            ImageContent(type="image", mimeType="image/jpeg", data="abc123"),
        ],
        structuredContent={"status": "ready"},
        isError=False,
    )

    messages = result_to_image_messages("observe", result)

    assert messages == [{
        "role": "user",
        "content": [
            {
                "type": "input_text",
                "text": "Images returned by MCP tool observe:",
            },
            {
                "type": "input_image",
                "image_url": "data:image/jpeg;base64,abc123",
                "detail": "high",
            },
        ],
    }]
