import dotenv
dotenv.load_dotenv()
from pydantic import BaseModel
import weave
from agents import Agent, Runner, function_tool, SQLiteSession
from agents.extensions.handoff_prompt import prompt_with_handoff_instructions

import asyncio
weave.init("openai-agents")

session = SQLiteSession("test_conversation")

class Weather(BaseModel):
    city: str
    temperature_range: str
    conditions: str

@function_tool
def get_weather(city: str) -> Weather:
    return Weather(city=city, temperature_range="14-20C", conditions="Sunny with wind.")


spanish_agent = Agent(
    name="Spanish agent",
    model="gpt-5-nano",
    instructions="You only speak Spanish. You are responsible for answering questions in Spanish. Please use the get_weather tool to get the weather forecast if the question is about the weather.",
    tools=[get_weather],
)

english_agent = Agent(
    name="English agent",
    model="gpt-5-nano",
    instructions="You only speak English. You are responsible for answering questions in English. Please use the get_weather tool to get the weather forecast.",
    tools=[get_weather],
)

triage_agent = Agent(
    name="Triage agent",
    model="gpt-5-nano",
    instructions=prompt_with_handoff_instructions(
        "Handoff to the appropriate agent based on the language of the request."
    ),
    handoffs=[spanish_agent, english_agent],
)


async def main():
    result = await Runner.run(triage_agent, input="Hi, what is the weather in Los Angeles?", session=session)
    print(result.final_output)
        # ¡Hola! Estoy bien, gracias por preguntar. ¿Y tú, cómo estás?

  


if __name__ == "__main__":
    asyncio.run(main())