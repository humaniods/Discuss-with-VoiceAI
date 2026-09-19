import unittest

import agent_config
from prompts import SYSTEM_PROMPT


class AgentConfigTests(unittest.TestCase):
    def test_registers_clock_and_live_search_as_flat_client_tools(self):
        tools = agent_config.build_agent_body()["tools"]

        self.assertEqual(
            {tool["name"] for tool in tools},
            {"get_current_datetime", "web_search"},
        )
        self.assertTrue(all(tool["type"] == "function" for tool in tools))
        self.assertTrue(all(tool["execution_mode"] == "interactive" for tool in tools))
        clock = next(tool for tool in tools if tool["name"] == "get_current_datetime")
        self.assertEqual(clock["parameters"]["properties"], {})
        self.assertEqual(clock["parameters"]["required"], [])

    def test_prompt_makes_dynamic_lookup_mandatory(self):
        self.assertIn("ALWAYS call get_current_datetime", SYSTEM_PROMPT)
        self.assertIn("ALWAYS call web_search", SYSTEM_PROMPT)
        self.assertIn("confident stale answer", SYSTEM_PROMPT)
        self.assertIn('"iPhone 18 Pro"', SYSTEM_PROMPT)
        self.assertIn('"6:04 PM"', SYSTEM_PROMPT)
        self.assertIn("never invent a plausible-sounding model", SYSTEM_PROMPT)

    def test_validation_rejects_a_missing_required_tool(self):
        body = agent_config.build_agent_body()
        body["tools"] = body["tools"][:1]

        with self.assertRaisesRegex(ValueError, "get_current_datetime and web_search"):
            agent_config._validate_agent_body(body)


if __name__ == "__main__":
    unittest.main()
