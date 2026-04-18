"""
Stage 2: call the LLM with raw CodeQL results to produce a draft mapping.
"""

from __future__ import annotations

import json
import os

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

_SYSTEM_PROMPT = """\
You are helping build a constraint verification system for a web app.
Given raw CodeQL scan results, generate a JSON mapping file that:
1. Assigns each element a logical camelCase name with a role suffix:
   - Action roles:    Btn, Input, Toggle, Form, Handle
   - Component roles: Display, List, Error, Counter, Text
2. Determines the correct read_property for each display element
   (textContent, innerHTML, innerText, or value).
3. Infers the kind (action or component) from the element type.
4. Groups API endpoints by logical name.

Return ONLY valid JSON, no explanation, matching exactly this schema:
{
  "elements": {
    "<camelCaseName>": {
      "selector":      "<CSS selector>",
      "tag":           "<html tag>",
      "kind":          "action" | "component",
      "role":          "<Btn|Input|Toggle|Form|Handle|Display|List|Error|Counter|Text>",
      "events":        ["<event>", ...],          // action elements only
      "read_property": "<textContent|...>",       // component elements only
      "file":          "<relative path>",
      "line":          <int>
    }
  },
  "apis": {
    "<camelCaseName>": {
      "endpoint": "<url or path>",
      "method":   "<GET|POST|PUT|DELETE|...>",
      "file":     "<relative path>",
      "line":     <int>
    }
  },
  "error_handlers": [
    { "file": "<relative path>", "line": <int> }
  ]
}\
"""


def generate_draft_mapping(raw_elements: dict) -> dict:
    """
    Send *raw_elements* to OpenAI and return the parsed draft mapping dict.
    """
    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

    response = client.chat.completions.create(
        model="gpt-4o",
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    "Generate the mapping for these elements:\n"
                    + json.dumps(raw_elements, indent=2)
                ),
            },
        ],
    )

    return json.loads(response.choices[0].message.content)
