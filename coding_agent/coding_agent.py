from agents import ModelSettings
from agency_swarm import Agent, WebSearchTool
from openai.types.shared import Reasoning
from coding_agent.tools import apply_patch, shell_tool, OpenAIImageGenerationTool, update_plan, DeployTool
coding_agent = Agent(
    name="CodingAgent",
    description="Vibe Code Any Website",
    instructions="./instructions.md",
    model="gpt-5.1-codex",
    tools = [
        apply_patch,
        shell_tool,
        WebSearchTool(),
        OpenAIImageGenerationTool,
        update_plan,
		    DeployTool
    ],
    model_settings=ModelSettings(
        reasoning=Reasoning(
            effort="medium",
           
        ),
    ),
)


