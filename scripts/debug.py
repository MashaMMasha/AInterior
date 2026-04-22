from obllomov.agents.llms import ChatMock, get_chat_yandex_model
from obllomov.schemas.domain.raw import RawWindowEntry 
from obllomov.agents.base import BaseAgent
from obllomov.agents.editors import SceneEditor


# llm = ChatMock()
llm = get_chat_yandex_model(max_completion_tokens=128)

agent = BaseAgent(llm)

system_prompt = """Here's your name: {name}"""

print(agent._str_plan(system_prompt,
                    input_variables={
                        "name": "Jarvis",
                        "query": "What is your name"
                    }))
