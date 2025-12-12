from agents import ModelSettings
from agency_swarm import Agent, WebSearchTool
from openai.types.shared import Reasoning
from coding_agent.tools import apply_patch, shell_tool, OpenAIImageGenerationTool, update_plan

coding_agent = Agent(
    name="CodingAgent",
    description="Vibe Code Any Website",
    instructions="./instructions.md",
    model="gpt-5.2-2025-12-11",
    tools = [
        apply_patch,
        shell_tool,
        WebSearchTool(),
        OpenAIImageGenerationTool,
        update_plan,
    ],
    model_settings=ModelSettings(
        reasoning=Reasoning(
            effort="medium",
           
        ),
    ),
)


